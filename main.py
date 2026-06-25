import telebot
from telebot import types
import sqlite3
import datetime
import requests
import threading
import time

# ===================== КОНФИГ =====================
BOT_TOKEN        = "8796598287:AAFK9lvJ_T3oVC4Xr3VH0U_ArmPmY4CskSs"       # @BotFather
CRYPTOBOT_TOKEN  = "582363:AALEf7JOugnrQyrkMHzH5UrO7pdOjjYnTQy"       # @CryptoBot → /pay → создай приложение
ADMIN_ID         = 8118184388                    # Ваш Telegram ID
ADMIN_USERNAME   = "@Xeltryx"
SUPPORT_USERNAME = "@Gaftes_Support"
SUPPORT_LINK     = "t.me/user"

# CryptoBot API — mainnet: pay.crypt.bot | testnet: testnet-pay.crypt.bot
CRYPTOBOT_API = "https://pay.crypt.bot/api"
# ==================================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ===================== CRYPTOBOT =====================
def cb_request(method, params=None):
    """Выполняет запрос к CryptoBot API."""
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    url = f"{CRYPTOBOT_API}/{method}"
    try:
        r = requests.post(url, json=params or {}, headers=headers, timeout=10)
        data = r.json()
        if data.get("ok"):
            return data["result"]
        else:
            print(f"[CryptoBot] Ошибка {method}: {data}")
            return None
    except Exception as e:
        print(f"[CryptoBot] Исключение: {e}")
        return None


def create_invoice(amount_usd, user_id, description="Пополнение баланса GAFTES"):
    """
    Создаёт инвойс через CryptoBot.
    CryptoBot сам конвертирует USD → крипту по курсу.
    Возвращает dict с ключами: invoice_id, pay_url
    """
    result = cb_request("createInvoice", {
        "currency_type": "fiat",
        "fiat":          "USD",
        "amount":        str(amount_usd),
        "description":   description,
        "payload":       f"{user_id}:{amount_usd}",   # наш payload для идентификации
        "paid_btn_name": "callback",
        "paid_btn_url":  f"https://t.me/{bot.get_me().username}",
        "allow_comments":  False,
        "allow_anonymous": False,
        "expires_in":    3600,                        # инвойс живёт 1 час
    })
    if result:
        return {
            "invoice_id": result["invoice_id"],
            "pay_url":    result["pay_url"],
        }
    return None


def check_invoice(invoice_id):
    """Проверяет статус инвойса. Возвращает 'paid' / 'active' / None."""
    result = cb_request("getInvoices", {"invoice_ids": str(invoice_id)})
    if result and result.get("items"):
        return result["items"][0].get("status")
    return None


# ===================== БД =====================
def init_db():
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            balance     REAL DEFAULT 0.0,
            spent       REAL DEFAULT 0.0,
            is_banned   INTEGER DEFAULT 0,
            ban_reason  TEXT DEFAULT '',
            ban_date    TEXT DEFAULT '',
            joined      TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT,
            price    REAL DEFAULT 5.0,
            item     TEXT,
            content  TEXT DEFAULT '',
            sold     INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            product_id  INTEGER,
            item        TEXT,
            content     TEXT DEFAULT '',
            amount      REAL,
            date        TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Таблица ожидающих инвойсов
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id  INTEGER PRIMARY KEY,
            user_id     INTEGER,
            amount      REAL,
            credited    REAL,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT
        )
    """)

    c.execute("INSERT OR IGNORE INTO settings VALUES ('status', 'WORK')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('price', '5.5')")

    # Миграции: добавляем колонки если их нет (для существующих БД)
    try:
        c.execute("ALTER TABLE products ADD COLUMN content TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE purchases ADD COLUMN content TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def save_invoice(invoice_id, user_id, amount, credited):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO invoices VALUES (?,?,?,?,'pending',?)",
        (invoice_id, user_id, amount, credited, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_pending_invoices():
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT invoice_id, user_id, amount, credited FROM invoices WHERE status='pending'")
    rows = c.fetchall()
    conn.close()
    return rows


def mark_invoice_paid(invoice_id):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("UPDATE invoices SET status='paid' WHERE invoice_id=?", (invoice_id,))
    conn.commit()
    conn.close()


def get_setting(key):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def set_setting(key, value):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


def register_user(user):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (user_id, username, first_name, joined) VALUES (?,?,?,?)",
            (user.id, user.username or "", user.first_name or "", datetime.date.today().isoformat())
        )
        conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row


def is_banned(user_id):
    u = get_user(user_id)
    return u and u[5] == 1


def update_balance(user_id, delta):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, user_id))
    conn.commit()
    conn.close()


def deduct_balance(user_id, amount):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ?, spent = spent + ? WHERE user_id=?",
              (amount, amount, user_id))
    conn.commit()
    conn.close()


def get_all_products_grouped():
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT name, price FROM products WHERE sold=0")
    groups = c.fetchall()
    conn.close()
    result = []
    for name, price in groups:
        conn2 = sqlite3.connect("gaftes.db")
        c2 = conn2.cursor()
        c2.execute("SELECT id, item, content FROM products WHERE name=? AND sold=0", (name,))
        items = c2.fetchall()
        conn2.close()
        result.append({"name": name, "price": price, "items": items})
    return result


def get_user_purchases(user_id):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("""
        SELECT p.item, p.content, pr.name, p.amount, p.date
        FROM purchases p
        JOIN products pr ON p.product_id = pr.id
        WHERE p.user_id=?
        ORDER BY p.date DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_users():
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_banned_users():
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT user_id, username, ban_date, ban_reason FROM users WHERE is_banned=1")
    rows = c.fetchall()
    conn.close()
    return rows


def ban_user(user_id, reason="Нарушение правил"):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1, ban_reason=?, ban_date=? WHERE user_id=?",
              (reason, datetime.date.today().isoformat(), user_id))
    conn.commit()
    conn.close()


def unban_user(user_id):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0, ban_reason='', ban_date='' WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_stats():
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*), SUM(amount) FROM purchases")
    row = c.fetchone()
    sales_count = row[0] or 0
    total_revenue = row[1] or 0.0
    today = datetime.date.today().isoformat()
    c.execute("SELECT SUM(amount) FROM purchases WHERE date LIKE ?", (today + "%",))
    today_revenue = c.fetchone()[0] or 0.0
    conn.close()
    return users_count, sales_count, total_revenue, today_revenue


# ===================== ФОНОВЫЙ ПОЛЛИНГ ИНВОЙСОВ =====================
def invoice_poller():
    """
    Каждые 5 секунд проверяет все pending-инвойсы через CryptoBot.
    Если оплачен — зачисляет баланс и уведомляет пользователя.
    """
    while True:
        try:
            pending = get_pending_invoices()
            for invoice_id, user_id, amount, credited in pending:
                status = check_invoice(invoice_id)
                if status == "paid":
                    mark_invoice_paid(invoice_id)
                    update_balance(user_id, credited)
                    commission = round(amount - credited, 2)
                    try:
                        bot.send_message(
                            user_id,
                            f"<b>✅ Оплата получена!</b>\n\n"
                            f"┌ 💰 Оплачено: <b>{amount:.2f}$</b>\n"
                            f"├ 📊 Комиссия (3%): <b>{commission:.2f}$</b>\n"
                            f"└ 👛 Зачислено: <b>{credited:.2f}$</b>\n\n"
                            f"Ваш баланс пополнен. Приятных покупок! 🛒",
                            reply_markup=kb_main()
                        )
                    except Exception as e:
                        print(f"[Poller] Не удалось уведомить {user_id}: {e}")
        except Exception as e:
            print(f"[Poller] Ошибка: {e}")
        time.sleep(5)


# ===================== СОСТОЯНИЯ =====================
user_states = {}


# ===================== КАСТОМНЫЕ ЭМОДЗИ =====================
# Замени ID на свои — формат: целое число в виде строки
EMOJI = {
    "profile":        "5368324170671202286",  # 👤
    "market":         "5372981976804366741",  # 🏪
    "support":        "5373026167722876724",  # 🎧
    "topup":          "5372914944804239028",  # 💎
    "back":           "5373027663268018522",  # ⬅️
    "money_5":        "5372914944804239028",  # 💵
    "money_10":       "5372914944804239028",
    "money_25":       "5372914944804239028",
    "money_50":       "5372914944804239028",
    "custom_amount":  "5368324170671202286",  # ✏️
    "pay":            "5373026167722876724",  # 💳
    "check":          "5372981976804366741",  # 🔄
    "cancel":         "5373027663268018522",  # ❌
    "buy":            "5372914944804239028",  # 🗃
    "purchases":      "5372981976804366741",  # 📦
    "to_market":      "5372981976804366741",  # 🏪
    "broadcast":      "5373026167722876724",  # 📢
    "stats":          "5368324170671202286",  # 📊
    "add_product":    "5372914944804239028",  # ➕
    "edit_product":   "5368324170671202286",  # 🛠
    "topup_user":     "5373026167722876724",  # 💳
    "bans":           "5373027663268018522",  # 🚫
    "toggle":         "5372981976804366741",  # 🟢
    "ban":            "5373027663268018522",  # ➕🚫
    "unban":          "5372914944804239028",  # ➖
    "change_price":   "5368324170671202286",  # ✏️
    "change_name":    "5368324170671202286",  # 📝
    "change_content": "5372981976804366741",  # 📄
    "change_stock":   "5372981976804366741",  # 📦
    "delete":         "5373027663268018522",  # ❌
    "refresh":        "5372981976804366741",  # 🔄
}

def btn(text: str, emoji_key: str, **kwargs) -> types.InlineKeyboardButton:
    """InlineKeyboardButton с icon_custom_emoji_id через прямой атрибут."""
    b = types.InlineKeyboardButton(text, **kwargs)
    eid = EMOJI.get(emoji_key)
    if eid:
        b.icon_custom_emoji_id = eid
    return b


# ===================== КЛАВИАТУРЫ =====================
def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn("Профиль", "profile", callback_data="profile"),
        btn("Маркет", "market", callback_data="market"),
    )
    kb.add(btn("Техподдержка", "support", url=f"https://{SUPPORT_LINK}"))
    return kb


def kb_profile():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(btn("Пополнить баланс", "topup", callback_data="topup"))
    kb.add(btn("Техподдержка", "support", url=f"https://{SUPPORT_LINK}"))
    kb.add(btn("Назад", "back", callback_data="back_main"))
    return kb


def kb_topup():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn("5$", "money_5", callback_data="topup_5"),
        btn("10$", "money_10", callback_data="topup_10"),
    )
    kb.add(
        btn("25$", "money_25", callback_data="topup_25"),
        btn("50$", "money_50", callback_data="topup_50"),
    )
    kb.add(btn("Своя сумма", "custom_amount", callback_data="topup_custom"))
    kb.add(btn("Назад", "back", callback_data="back_profile"))
    return kb


def kb_pay(pay_url):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(btn("Оплатить через CryptoBot", "pay", url=pay_url))
    kb.add(btn("Проверить оплату", "check", callback_data="check_payment"))
    kb.add(btn("Отмена", "cancel", callback_data="topup"))
    return kb


def kb_support():
    kb = types.InlineKeyboardMarkup()
    kb.add(btn("Назад", "back", callback_data="back_main"))
    return kb


def kb_market(group):
    kb = types.InlineKeyboardMarkup(row_width=1)
    name = group["name"]
    price = group["price"]
    kb.add(btn(f"Купить 1 шт — ${price:.2f}", "buy", callback_data=f"buy_{name}_1"))
    kb.add(btn(f"Купить 5 шт — ${price*5:.2f}", "buy", callback_data=f"buy_{name}_5"))
    kb.add(btn(f"Купить 10 шт — ${price*10:.2f}", "buy", callback_data=f"buy_{name}_10"))
    kb.add(btn("Назад", "back", callback_data="back_main"))
    return kb


def kb_after_purchase():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn("Мои покупки", "purchases", callback_data="my_purchases"),
        btn("В маркет", "to_market", callback_data="market"),
    )
    return kb


def kb_my_purchases():
    kb = types.InlineKeyboardMarkup()
    kb.add(btn("Назад", "back", callback_data="back_main"))
    return kb


def kb_admin():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn("Рассылка", "broadcast", callback_data="admin_broadcast"),
        btn("Статистика", "stats", callback_data="admin_stats"),
    )
    kb.add(
        btn("Добавить товар", "add_product", callback_data="admin_add_product"),
        btn("Редакция товара", "edit_product", callback_data="admin_edit_product"),
    )
    kb.add(
        btn("Пополнить баланс", "topup_user", callback_data="admin_topup_user"),
        btn("Баны", "bans", callback_data="admin_bans"),
    )
    kb.add(btn("Вкл/Выкл бота", "toggle", callback_data="admin_toggle_status"))
    return kb


def kb_bans():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn("Забанить", "ban", callback_data="admin_ban"),
        btn("Разбанить", "unban", callback_data="admin_unban"),
    )
    kb.add(btn("Назад", "back", callback_data="admin_panel"))
    return kb


def kb_cancel_admin():
    kb = types.InlineKeyboardMarkup()
    kb.add(btn("Отмена", "cancel", callback_data="admin_panel"))
    return kb


def kb_cancel_topup():
    kb = types.InlineKeyboardMarkup()
    kb.add(btn("Отмена", "cancel", callback_data="topup"))
    return kb


def kb_admin_edit():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn("Изменить цену", "change_price", callback_data="admin_change_price"),
        btn("Изменить название", "change_name", callback_data="admin_change_name"),
    )
    kb.add(
        btn("Изменить контент", "change_content", callback_data="admin_change_content"),
        btn("Изменить остаток", "change_stock", callback_data="admin_change_stock"),
    )
    kb.add(btn("Удалить товар", "delete", callback_data="admin_delete_product"))
    kb.add(btn("Назад", "back", callback_data="admin_panel"))
    return kb


def kb_stats():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn("Обновить", "refresh", callback_data="admin_stats"),
        btn("Назад", "back", callback_data="admin_panel"),
    )
    return kb


# ===================== ТЕКСТЫ =====================
def text_start():
    status = get_setting("status")
    price = get_setting("price")
    st_icon = "🟢" if status == "WORK" else "🔴"
    return (
        f"<b>👋 Добро пожаловать в GAFTES!</b>\n\n"
        f"┌ {st_icon} Статус бота: <b>{status}</b>\n"
        f"└ 💰 Ценник: <b>{price}$</b>"
    )


def text_profile(user_id):
    u = get_user(user_id)
    name = u[2] or "—"
    username = f"@{u[1]}" if u[1] else "—"
    balance = u[3]
    spent = u[4]
    return (
        f"<b>🪪 ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        f"┌ 👤 Имя: <b>{name}</b>\n"
        f"├ 🤖 Юзернейм: <b>{username}</b>\n"
        f"└ ⭐️ ID: <code>{user_id}</code>\n\n"
        f"┌ 👛 Баланс: <b>{balance:.2f}$</b>\n"
        f"└ 📈 Потрачено всего: <b>{spent:.2f}$</b>"
    )


def text_topup_menu():
    return (
        "<b>💎 Пополнение через CryptoBot</b>\n"
        "Выберите сумму или введите свою:"
    )


def text_market_render(user_id, group):
    u = get_user(user_id)
    balance = u[3] if u else 0.0
    name = group["name"]
    price = group["price"]
    stock = len(group["items"])
    return (
        f"<b>🏪 МАРКЕТ GAFTES</b>\n\n"
        f"┌ 📲 <b>{name}</b>\n"
        f"│\n"
        f"│ 👛 Ваш баланс: <b>${balance:.2f}</b>\n"
        f"│ 💵 Цена: <b>${price:.2f}</b>\n"
        f"│ 📦 В наличии: <b>{stock} шт.</b>\n"
        f"└ 🛒 Выберите количество:"
    )


def text_support():
    return (
        f"<b>🎧 ТЕХПОДДЕРЖКА GAFTES</b>\n\n"
        f"По всем вопросам пишите:\n"
        f"👉 {SUPPORT_USERNAME}\n"
        f"👉 {SUPPORT_LINK}"
    )


def text_my_purchases(user_id):
    purchases = get_user_purchases(user_id)
    if not purchases:
        return "<b>📦 МОИ ПОКУПКИ</b>\n\nПокупок пока нет."
    from collections import defaultdict
    groups = defaultdict(list)
    totals = defaultdict(float)
    for item, content, name, amount, date in purchases:
        groups[name].append((item, content))
        totals[name] += amount
    text = "<b>📦 МОИ ПОКУПКИ</b>\n\n"
    delivery_shown = set()
    for name, entries in groups.items():
        text += f"┌ 📲 <b>{name}</b>\n"
        for item, content in entries:
            text += f"│ <code>{item}</code>\n"
        if entries and entries[0][1] and name not in delivery_shown:
            text += f"│ {entries[0][1]}\n"
            delivery_shown.add(name)
        text += f"└ 💰 Потрачено: <b>${totals[name]:.2f}</b>\n\n"
    return text.strip()


def text_admin_panel():
    status = get_setting("status")
    price = get_setting("price")
    st_icon = "🟢" if status == "WORK" else "🔴"
    return (
        f"<b>⚙️ АДМИН-ПАНЕЛЬ GAFTES</b>\n\n"
        f"┌ 👑 Админ: <b>{ADMIN_USERNAME}</b>\n"
        f"├ {st_icon} Статус: <b>{status}</b>\n"
        f"└ 💰 Ценник: <b>{price}$</b>"
    )


def text_bans():
    banned = get_banned_users()
    text = "<b>🚫 БАНЫ</b>\n\n"
    if not banned:
        return text + "Забаненных пользователей нет."
    for uid, username, ban_date, ban_reason in banned:
        uname = f"@{username}" if username else str(uid)
        text += (
            f"┌ 👤 <b>{uname}</b>\n"
            f"├ ID: <code>{uid}</code>\n"
            f"├ 📅 Забанен: <b>{ban_date}</b>\n"
            f"└ 📝 Причина: {ban_reason}\n\n"
        )
    return text.strip()


def text_edit_product():
    groups = get_all_products_grouped()
    text = "<b>🛠 РЕДАКЦИЯ ТОВАРА</b>\nТекущие товары:\n\n"
    if not groups:
        return text + "Товаров нет."
    for g in groups:
        text += f"┌ 📲 <b>{g['name']}</b>  |  💰 <b>${g['price']:.2f}</b>\n"
        for pid, item, content in g["items"]:
            text += f"│ <code>{item}</code>"
            if content:
                text += f"  — {content}"
            text += "\n"
        text += "└\n\n"
    return text.strip()


def text_stats():
    users_count, sales_count, total_revenue, today_revenue = get_stats()
    status = get_setting("status")
    st_icon = "🟢" if status == "WORK" else "🔴"
    return (
        f"<b>📊 СТАТИСТИКА</b>\n\n"
        f"┌ 👥 Пользователей: <b>{users_count}</b>\n"
        f"├ 🛒 Продаж: <b>{sales_count}</b>\n"
        f"├ 💰 Оборот: <b>${total_revenue:.2f}</b>\n"
        f"├ {st_icon} Статус: <b>{status}</b>\n"
        f"└ 📅 Сегодня: <b>+${today_revenue:.2f}</b>"
    )


# ===================== УТИЛИТА: создать и отправить инвойс =====================
def send_invoice(chat_id, user_id, amount, message_id=None):
    """Создаёт инвойс CryptoBot и редактирует сообщение (или отправляет новое)."""
    commission = round(amount * 0.03, 2)
    credited   = round(amount - commission, 2)

    invoice = create_invoice(amount, user_id)
    if not invoice:
        text = "❌ Ошибка создания инвойса. Попробуйте позже или обратитесь в поддержку."
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb_topup())
        else:
            bot.send_message(chat_id, text, reply_markup=kb_topup())
        return

    save_invoice(invoice["invoice_id"], user_id, amount, credited)

    text = (
        f"<b>💎 Счёт на оплату создан!</b>\n\n"
        f"┌ 💰 К оплате: <b>{amount:.2f}$</b>\n"
        f"├ 📊 Комиссия (3%): <b>{commission:.2f}$</b>\n"
        f"└ ✅ Зачислится: <b>{credited:.2f}$</b>\n\n"
        f"Нажмите кнопку ниже для оплаты.\n"
        f"⏳ Счёт действует <b>1 час</b>."
    )
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb_pay(invoice["pay_url"]))
    else:
        bot.send_message(chat_id, text, reply_markup=kb_pay(invoice["pay_url"]))


# ===================== ХЭНДЛЕРЫ =====================
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    register_user(msg.from_user)
    if is_banned(msg.from_user.id):
        bot.send_message(msg.chat.id, "🚫 Вы заблокированы в этом боте.")
        return
    bot.send_message(msg.chat.id, text_start(), reply_markup=kb_main())


@bot.message_handler(commands=["admin"])
def cmd_admin(msg):
    if msg.from_user.id != ADMIN_ID:
        bot.send_message(msg.chat.id, "⛔️ Нет доступа.")
        return
    bot.send_message(msg.chat.id, text_admin_panel(), reply_markup=kb_admin())


# ===================== CALLBACK =====================
@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    uid  = call.from_user.id
    cid  = call.message.chat.id
    mid  = call.message.message_id
    data = call.data

    if is_banned(uid) and data != "back_main":
        bot.answer_callback_query(call.id, "🚫 Вы заблокированы.")
        return

    # ── ГЛАВНОЕ МЕНЮ ──
    if data == "back_main":
        bot.edit_message_text(text_start(), cid, mid, reply_markup=kb_main())

    elif data == "profile":
        bot.edit_message_text(text_profile(uid), cid, mid, reply_markup=kb_profile())

    elif data == "support":
        bot.edit_message_text(text_support(), cid, mid, reply_markup=kb_support())

    elif data == "market":
        groups = get_all_products_grouped()
        if not groups:
            no_kb = types.InlineKeyboardMarkup()
            no_kb.add(btn("Назад", "back", callback_data="back_main"))
            bot.edit_message_text("<b>🏪 МАРКЕТ GAFTES</b>\n\nТоваров пока нет.", cid, mid, reply_markup=no_kb)
        else:
            g = groups[0]
            bot.edit_message_text(text_market_render(uid, g), cid, mid, reply_markup=kb_market(g))

    elif data == "back_profile":
        bot.edit_message_text(text_profile(uid), cid, mid, reply_markup=kb_profile())

    # ── ПОПОЛНЕНИЕ ──
    elif data == "topup":
        bot.edit_message_text(text_topup_menu(), cid, mid, reply_markup=kb_topup())

    elif data in ("topup_5", "topup_10", "topup_25", "topup_50"):
        amount = float(data.split("_")[1])
        bot.answer_callback_query(call.id, "⏳ Создаём инвойс...")
        send_invoice(cid, uid, amount, mid)
        return

    elif data == "topup_custom":
        user_states[uid] = "awaiting_topup_amount"
        bot.edit_message_text(
            "<b>💵 Введите сумму пополнения</b>\nПример: <code>15</code>",
            cid, mid, reply_markup=kb_cancel_topup()
        )

    elif data == "check_payment":
        # Ручная проверка — пользователь нажал кнопку
        pending = get_pending_invoices()
        user_pending = [p for p in pending if p[1] == uid]
        if not user_pending:
            bot.answer_callback_query(call.id, "✅ Нет ожидающих платежей.", show_alert=True)
        else:
            inv_id, _, amount, credited = user_pending[-1]
            status = check_invoice(inv_id)
            if status == "paid":
                mark_invoice_paid(inv_id)
                update_balance(uid, credited)
                commission = round(amount - credited, 2)
                bot.answer_callback_query(call.id, "✅ Оплата подтверждена!", show_alert=True)
                bot.edit_message_text(
                    f"<b>✅ Оплата получена!</b>\n\n"
                    f"┌ 💰 Оплачено: <b>{amount:.2f}$</b>\n"
                    f"├ 📊 Комиссия (3%): <b>{commission:.2f}$</b>\n"
                    f"└ 👛 Зачислено: <b>{credited:.2f}$</b>",
                    cid, mid, reply_markup=kb_profile()
                )
            elif status == "active":
                bot.answer_callback_query(call.id, "⏳ Оплата ещё не получена. Попробуйте позже.", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ Инвойс истёк или отменён.", show_alert=True)

    # ── ПОКУПКА ──
    elif data.startswith("buy_"):
        parts = data.split("_")
        qty   = int(parts[-1])
        name  = "_".join(parts[1:-1])

        groups = get_all_products_grouped()
        group  = next((g for g in groups if g["name"] == name), None)
        if not group:
            bot.answer_callback_query(call.id, "Товар не найден.")
            return

        price = group["price"]
        total = price * qty
        u = get_user(uid)
        if u[3] < total:
            bot.answer_callback_query(call.id, f"❌ Недостаточно средств. Нужно ${total:.2f}", show_alert=True)
            return
        if len(group["items"]) < qty:
            bot.answer_callback_query(call.id, "❌ Недостаточно товаров в наличии.", show_alert=True)
            return

        items_to_sell = group["items"][:qty]
        bought_lines  = []
        conn = sqlite3.connect("gaftes.db")
        c = conn.cursor()
        for pid, item, content in items_to_sell:
            c.execute("UPDATE products SET sold=1 WHERE id=?", (pid,))
            c.execute(
                "INSERT INTO purchases (user_id, product_id, item, content, amount, date) VALUES (?,?,?,?,?,?)",
                (uid, pid, item, content, price, datetime.datetime.now().isoformat())
            )
            bought_lines.append((item, content))
        conn.commit()
        conn.close()
        deduct_balance(uid, total)

        items_text = "\n".join(f"<code>{item}</code>" for item, _ in bought_lines)
        delivery_content = bought_lines[0][1] if bought_lines else ""

        msg_text = (
            f"<b>✅ ПОКУПКА УСПЕШНА!</b>\n\n"
            f"🗃 Товар: <b>{name}</b>\n"
            f"💰 Списано: <b>${total:.2f}</b>\n\n"
            f"📲 <b>Ваш товар:</b>\n{items_text}"
        )
        if delivery_content:
            msg_text += f"\n\n{delivery_content}"

        bot.edit_message_text(msg_text, cid, mid, reply_markup=kb_after_purchase())

    elif data == "my_purchases":
        bot.edit_message_text(text_my_purchases(uid), cid, mid, reply_markup=kb_my_purchases())

    # ── АДМИН ──
    elif data == "admin_panel":
        if uid != ADMIN_ID:
            return
        user_states.pop(uid, None)
        bot.edit_message_text(text_admin_panel(), cid, mid, reply_markup=kb_admin())

    elif data == "admin_toggle_status":
        if uid != ADMIN_ID:
            return
        cur = get_setting("status")
        set_setting("status", "STOP" if cur == "WORK" else "WORK")
        bot.edit_message_text(text_admin_panel(), cid, mid, reply_markup=kb_admin())

    elif data == "admin_stats":
        if uid != ADMIN_ID:
            return
        bot.edit_message_text(text_stats(), cid, mid, reply_markup=kb_stats())

    elif data == "admin_bans":
        if uid != ADMIN_ID:
            return
        bot.edit_message_text(text_bans(), cid, mid, reply_markup=kb_bans())

    elif data == "admin_ban":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_ban_id"
        bot.edit_message_text(
            "<b>🚫 БАН</b>\n\nФормат: <code>ID | причина</code>\nПример: <code>123456789 | Спам</code>",
            cid, mid, reply_markup=kb_cancel_admin()
        )

    elif data == "admin_unban":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_unban_id"
        bot.edit_message_text("<b>✅ РАЗБАН</b>\n\nВведите ID пользователя:", cid, mid, reply_markup=kb_cancel_admin())

    elif data == "admin_broadcast":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_broadcast"
        bot.edit_message_text(
            "<b>📢 РАССЫЛКА</b>\n\nВведите текст — он будет отправлен всем пользователям:",
            cid, mid, reply_markup=kb_cancel_admin()
        )

    elif data == "admin_add_product":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_new_product"
        bot.edit_message_text(
            "<b>➕ ДОБАВЛЕНИЕ ТОВАРА</b>\n\n"
            "Формат каждой строки:\n"
            "<code>Название | данные_товара | контент при выдаче</code>\n\n"
            "Пример:\n"
            "<code>MAX TOKEN | login:password | Инструкция: t.me/guide</code>\n\n"
            "⚠️ Третье поле (контент) — необязательно.",
            cid, mid, reply_markup=kb_cancel_admin()
        )

    elif data == "admin_edit_product":
        if uid != ADMIN_ID:
            return
        bot.edit_message_text(text_edit_product(), cid, mid, reply_markup=kb_admin_edit())

    elif data == "admin_change_price":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_new_price"
        bot.edit_message_text(
            "<b>✏️ ИЗМЕНЕНИЕ ЦЕНЫ</b>\n\nФормат: <code>Название | цена</code>\nПример: <code>MAX TOKEN | 7.50</code>",
            cid, mid, reply_markup=kb_cancel_admin()
        )

    elif data == "admin_change_name":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_new_name"
        bot.edit_message_text(
            "<b>📝 ИЗМЕНЕНИЕ НАЗВАНИЯ</b>\n\nФормат: <code>старое | новое</code>",
            cid, mid, reply_markup=kb_cancel_admin()
        )

    elif data == "admin_change_content":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_new_content"
        bot.edit_message_text(
            "<b>📄 ИЗМЕНЕНИЕ КОНТЕНТА ПРИ ВЫДАЧЕ</b>\n\n"
            "Формат: <code>Название | текст</code>\n"
            "Пример: <code>MAX TOKEN | Поддержка: @support</code>",
            cid, mid, reply_markup=kb_cancel_admin()
        )

    elif data == "admin_change_stock":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_change_stock"
        bot.edit_message_text(
            "<b>📦 ИЗМЕНЕНИЕ ОСТАТКА</b>\n\n"
            "Формат: <code>Название | новое_количество</code>\n"
            "Пример: <code>MAX TOKEN | 50</code>\n\n"
            "⚠️ Лишние единицы будут удалены, если указать меньше текущего.",
            cid, mid, reply_markup=kb_cancel_admin()
        )

    elif data == "admin_delete_product":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_delete_product"
        bot.edit_message_text("<b>❌ УДАЛЕНИЕ</b>\n\nВведите название товара:", cid, mid, reply_markup=kb_cancel_admin())

    elif data == "admin_topup_user":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_topup_user"
        bot.edit_message_text(
            "<b>💳 ПОПОЛНЕНИЕ БАЛАНСА ЮЗЕРА</b>\n\nФормат: <code>ID | сумма</code>\nПример: <code>123456789 | 10.00</code>",
            cid, mid, reply_markup=kb_cancel_admin()
        )

    bot.answer_callback_query(call.id)


# ===================== ТЕКСТОВЫЕ СООБЩЕНИЯ =====================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def on_text(msg):
    uid   = msg.from_user.id
    text  = msg.text.strip()
    state = user_states.get(uid)

    if is_banned(uid):
        bot.send_message(msg.chat.id, "🚫 Вы заблокированы.")
        return

    # ── Своя сумма пополнения ──
    if state == "awaiting_topup_amount":
        try:
            amount = float(text.replace(",", "."))
            if amount < 1:
                bot.send_message(msg.chat.id, "❌ Минимальная сумма — 1$")
                return
            user_states.pop(uid, None)
            send_invoice(msg.chat.id, uid, amount, None)
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Введите число. Пример: <code>15</code>")

    # ── Рассылка ──
    elif state == "awaiting_broadcast" and uid == ADMIN_ID:
        all_users = get_all_users()
        sent = failed = 0
        for target_id in all_users:
            try:
                bot.send_message(target_id, f"<b>📢 Сообщение от GAFTES:</b>\n\n{text}")
                sent += 1
            except Exception:
                failed += 1
        user_states.pop(uid, None)
        bot.send_message(
            msg.chat.id,
            f"<b>📢 Рассылка завершена!</b>\n✅ Отправлено: <b>{sent}</b>\n❌ Ошибок: <b>{failed}</b>",
            reply_markup=types.InlineKeyboardMarkup().add(
                btn("Назад", "back", callback_data="admin_panel"))
        )

    # ── Добавление товара ──
    elif state == "awaiting_new_product" and uid == ADMIN_ID:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        conn  = sqlite3.connect("gaftes.db")
        c     = conn.cursor()
        added = errors = 0
        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                name    = parts[0]
                item    = parts[1]
                content = parts[2] if len(parts) >= 3 else ""
                c2      = conn.cursor()
                c2.execute("SELECT price FROM products WHERE name=? LIMIT 1", (name,))
                pr    = c2.fetchone()
                price = pr[0] if pr else float(get_setting("price") or 5.0)
                c.execute("INSERT INTO products (name, price, item, content) VALUES (?,?,?,?)",
                          (name, price, item, content))
                added += 1
            else:
                errors += 1
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        bot.send_message(
            msg.chat.id,
            f"<b>✅ Добавлено: {added} шт.</b>" + (f"\n❌ Неверных строк: {errors}" if errors else ""),
            reply_markup=types.InlineKeyboardMarkup().add(
                btn("Назад", "back", callback_data="admin_panel"))
        )

    # ── Изменить цену ──
    elif state == "awaiting_new_price" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) == 2:
            try:
                name      = parts[0]
                new_price = float(parts[1].replace(",", ".").replace("$", ""))
                conn = sqlite3.connect("gaftes.db")
                conn.execute("UPDATE products SET price=? WHERE name=?", (new_price, name))
                conn.commit()
                conn.close()
                user_states.pop(uid, None)
                bot.send_message(
                    msg.chat.id, f"<b>✅ Цена «{name}» → ${new_price:.2f}</b>",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        btn("Назад", "back", callback_data="admin_panel"))
                )
            except ValueError:
                bot.send_message(msg.chat.id, "❌ Неверная цена.")
        else:
            bot.send_message(msg.chat.id, "❌ Формат: Название | цена")

    # ── Изменить название ──
    elif state == "awaiting_new_name" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) == 2:
            old_name, new_name = parts
            conn = sqlite3.connect("gaftes.db")
            conn.execute("UPDATE products SET name=? WHERE name=?", (new_name, old_name))
            conn.commit()
            conn.close()
            user_states.pop(uid, None)
            bot.send_message(
                msg.chat.id, f"<b>✅ «{old_name}» → «{new_name}»</b>",
                reply_markup=types.InlineKeyboardMarkup().add(
                    btn("Назад", "back", callback_data="admin_panel"))
            )
        else:
            bot.send_message(msg.chat.id, "❌ Формат: старое | новое")

    # ── Изменить контент ──
    elif state == "awaiting_new_content" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|", 1)]
        if len(parts) == 2:
            name, new_content = parts
            conn = sqlite3.connect("gaftes.db")
            conn.execute("UPDATE products SET content=? WHERE name=? AND sold=0", (new_content, name))
            conn.commit()
            conn.close()
            user_states.pop(uid, None)
            bot.send_message(
                msg.chat.id,
                f"<b>✅ Контент для «{name}» обновлён!</b>\n\nПри покупке покупатель увидит:\n<i>{new_content}</i>",
                reply_markup=types.InlineKeyboardMarkup().add(
                    btn("Назад", "back", callback_data="admin_panel"))
            )
        else:
            bot.send_message(msg.chat.id, "❌ Формат: Название | текст")

    # ── Изменить остаток ──
    elif state == "awaiting_change_stock" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) == 2:
            try:
                name      = parts[0]
                new_stock = int(parts[1])
                if new_stock < 0:
                    raise ValueError
                conn = sqlite3.connect("gaftes.db")
                c    = conn.cursor()
                # Текущий остаток
                c.execute("SELECT id FROM products WHERE name=? AND sold=0 ORDER BY id ASC", (name,))
                current_ids = [r[0] for r in c.fetchall()]
                current_stock = len(current_ids)
                if new_stock < current_stock:
                    # Удаляем лишние (с конца)
                    to_delete = current_ids[new_stock:]
                    conn.executemany("DELETE FROM products WHERE id=?", [(i,) for i in to_delete])
                    diff_text = f"Удалено {current_stock - new_stock} шт."
                elif new_stock > current_stock:
                    # Берём шаблон из существующего товара
                    c.execute("SELECT name, price, item, content FROM products WHERE name=? LIMIT 1", (name,))
                    tmpl = c.fetchone()
                    if not tmpl:
                        bot.send_message(msg.chat.id, f"❌ Товар «{name}» не найден.")
                        conn.close()
                        return
                    t_name, t_price, t_item, t_content = tmpl
                    add_count = new_stock - current_stock
                    for _ in range(add_count):
                        conn.execute(
                            "INSERT INTO products (name, price, item, content, sold) VALUES (?,?,?,?,0)",
                            (t_name, t_price, t_item, t_content)
                        )
                    diff_text = f"Добавлено {add_count} шт."
                else:
                    diff_text = "Остаток не изменился."
                conn.commit()
                conn.close()
                user_states.pop(uid, None)
                bot.send_message(
                    msg.chat.id,
                    f"<b>✅ Остаток «{name}»: {new_stock} шт.</b>\n{diff_text}",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        btn("Назад", "back", callback_data="admin_panel"))
                )
            except ValueError:
                bot.send_message(msg.chat.id, "❌ Введите целое число ≥ 0.")
        else:
            bot.send_message(msg.chat.id, "❌ Формат: Название | количество")

    # ── Удалить товар ──
    elif state == "awaiting_delete_product" and uid == ADMIN_ID:
        conn = sqlite3.connect("gaftes.db")
        cur  = conn.execute("DELETE FROM products WHERE name=? AND sold=0", (text,))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        bot.send_message(
            msg.chat.id, f"<b>✅ Удалено {deleted} шт. «{text}»</b>",
            reply_markup=types.InlineKeyboardMarkup().add(
                btn("Назад", "back", callback_data="admin_panel"))
        )

    # ── Бан ──
    elif state == "awaiting_ban_id" and uid == ADMIN_ID:
        parts        = [p.strip() for p in text.split("|")]
        target_input = parts[0]
        reason       = parts[1] if len(parts) > 1 else "Нарушение правил"
        try:
            target_id = int(target_input)
        except ValueError:
            uname = target_input.lstrip("@")
            conn  = sqlite3.connect("gaftes.db")
            c     = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE username=?", (uname,))
            row = c.fetchone()
            conn.close()
            if not row:
                bot.send_message(msg.chat.id, "❌ Пользователь не найден в БД.")
                return
            target_id = row[0]
        ban_user(target_id, reason)
        user_states.pop(uid, None)
        bot.send_message(
            msg.chat.id,
            f"<b>🚫 Пользователь <code>{target_id}</code> забанен.</b>\nПричина: {reason}",
            reply_markup=types.InlineKeyboardMarkup().add(
                btn("Назад", "back", callback_data="admin_panel"))
        )

    # ── Разбан ──
    elif state == "awaiting_unban_id" and uid == ADMIN_ID:
        try:
            target_id = int(text)
            unban_user(target_id)
            user_states.pop(uid, None)
            bot.send_message(
                msg.chat.id, f"<b>✅ Пользователь <code>{target_id}</code> разбанен.</b>",
                reply_markup=types.InlineKeyboardMarkup().add(
                    btn("Назад", "back", callback_data="admin_panel"))
            )
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Введите числовой ID.")

    # ── Пополнение юзера (админ) ──
    elif state == "awaiting_topup_user" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) == 2:
            try:
                target_id = int(parts[0])
                amount    = float(parts[1].replace(",", ".").replace("$", ""))
                update_balance(target_id, amount)
                user_states.pop(uid, None)
                bot.send_message(
                    msg.chat.id,
                    f"<b>✅ Баланс <code>{target_id}</code> пополнен на ${amount:.2f}</b>",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        btn("Назад", "back", callback_data="admin_panel"))
                )
                try:
                    bot.send_message(target_id, f"<b>💳 Ваш баланс пополнен на ${amount:.2f} администратором.</b>")
                except Exception:
                    pass
            except ValueError:
                bot.send_message(msg.chat.id, "❌ Неверный формат.")
        else:
            bot.send_message(msg.chat.id, "❌ Формат: ID | сумма")

    else:
        bot.send_message(msg.chat.id, text_start(), reply_markup=kb_main())


# ===================== ЗАПУСК =====================
if __name__ == "__main__":
    init_db()
    # Запускаем фоновый поллинг инвойсов в отдельном потоке
    t = threading.Thread(target=invoice_poller, daemon=True)
    t.start()
    print("✅ GAFTES Bot запущен...")
    bot.infinity_polling(skip_pending=True)
