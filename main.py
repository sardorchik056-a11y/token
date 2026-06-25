import telebot
from telebot import types
import sqlite3
import datetime

# ===================== КОНФИГ =====================
BOT_TOKEN = "8796598287:AAFK9lvJ_T3oVC4Xr3VH0U_ArmPmY4CskSs"
ADMIN_ID = 8118184388          # Замените на ваш Telegram ID
ADMIN_USERNAME = "@Xeltryx"   # Замените на ваш username
SUPPORT_USERNAME = "@Gaftes_Support"
SUPPORT_LINK = "t.me/user"
CRYPTOBOT_TOKEN = "582363:AALEf7JOugnrQyrkMHzH5UrO7pdOjjYnTQy"  # Токен CryptoBot
# ==================================================

bot = telebot.TeleBot(BOT_TOKEN)

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
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT,
            price   REAL DEFAULT 5.0,
            item    TEXT,
            sold    INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            product_id  INTEGER,
            item        TEXT,
            amount      REAL,
            date        TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key     TEXT PRIMARY KEY,
            value   TEXT
        )
    """)

    # Дефолтные настройки
    c.execute("INSERT OR IGNORE INTO settings VALUES ('status', 'WORK')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('price', '5.5')")

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
    return row  # (user_id, username, first_name, balance, spent, is_banned, ban_reason, ban_date, joined)


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


def get_products():
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE sold=0", )
    rows = c.fetchall()
    conn.close()
    return rows  # (id, name, price, item, sold)


def get_all_products_grouped():
    """Возвращает товары сгруппированные по названию."""
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT name, price FROM products WHERE sold=0")
    groups = c.fetchall()
    conn.close()
    result = []
    for name, price in groups:
        conn2 = sqlite3.connect("gaftes.db")
        c2 = conn2.cursor()
        c2.execute("SELECT id, item FROM products WHERE name=? AND sold=0", (name,))
        items = c2.fetchall()
        conn2.close()
        result.append({"name": name, "price": price, "items": items})
    return result


def get_user_purchases(user_id):
    conn = sqlite3.connect("gaftes.db")
    c = conn.cursor()
    c.execute("""
        SELECT p.item, pr.name, p.amount, p.date
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


# Хранилище состояний
user_states = {}


# ===================== КЛАВИАТУРЫ =====================
def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🎧 Техподдержка", callback_data="support"),
        types.InlineKeyboardButton("🏪 Маркет", callback_data="market"),
    )
    return kb


def kb_profile():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🪪 Пополнить баланс", callback_data="topup"),
        types.InlineKeyboardButton("🎧 Техподдержка", callback_data="support"),
    )
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    return kb


def kb_topup():
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("💵 5$", callback_data="topup_5"),
        types.InlineKeyboardButton("💵 10$", callback_data="topup_10"),
        types.InlineKeyboardButton("💵 25$", callback_data="topup_25"),
    )
    kb.add(
        types.InlineKeyboardButton("💵 50$", callback_data="topup_50"),
        types.InlineKeyboardButton("💵 Своя сумма", callback_data="topup_custom"),
    )
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_profile"))
    return kb


def kb_support():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    return kb


def kb_market(product_group):
    kb = types.InlineKeyboardMarkup(row_width=1)
    name = product_group["name"]
    price = product_group["price"]
    kb.add(
        types.InlineKeyboardButton(f"🗃 Купить 1 шт — ${price:.2f}", callback_data=f"buy_{name}_1"),
        types.InlineKeyboardButton(f"🗃 Купить 5 шт — ${price * 5:.2f}", callback_data=f"buy_{name}_5"),
        types.InlineKeyboardButton(f"🗃 Купить 10 шт — ${price * 10:.2f}", callback_data=f"buy_{name}_10"),
    )
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    return kb


def kb_after_purchase():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📦 Мои покупки", callback_data="my_purchases"),
        types.InlineKeyboardButton("⬅️ В маркет", callback_data="market"),
    )
    return kb


def kb_my_purchases():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    return kb


def kb_admin():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🛠 Редакция товара и цены", callback_data="admin_edit_product"),
    )
    kb.add(
        types.InlineKeyboardButton("💳 Пополнение баланса", callback_data="admin_topup_user"),
        types.InlineKeyboardButton("🚫 Баны", callback_data="admin_bans"),
    )
    kb.add(
        types.InlineKeyboardButton("➕ Добавление товара", callback_data="admin_add_product"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
    )
    return kb


def kb_bans():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Забанить", callback_data="admin_ban"),
        types.InlineKeyboardButton("➖ Разбанить", callback_data="admin_unban"),
    )
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
    return kb


def kb_cancel():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel"))
    return kb


def kb_admin_edit():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✏️ Изменить цену", callback_data="admin_change_price"),
        types.InlineKeyboardButton("📝 Изменить название", callback_data="admin_change_name"),
    )
    kb.add(types.InlineKeyboardButton("❌ Удалить товар", callback_data="admin_delete_product"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
    return kb


def kb_stats():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"),
    )
    return kb


def kb_save_cancel():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Сохранить", callback_data="admin_save_product"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel"),
    )
    return kb


# ===================== ТЕКСТЫ =====================
def text_start():
    status = get_setting("status")
    price = get_setting("price")
    status_icon = "🟢" if status == "WORK" else "🔴"
    status_text = f"WORK 🟢" if status == "WORK" else f"STOP 🔴"
    return (
        f"👤 Добро пожаловать в GAFTES!\n"
        f"┌ Статус работы бота: {status_text}\n"
        f"└ Ценник: {price}$"
    )


def text_profile(user_id):
    u = get_user(user_id)
    name = u[2] or "—"
    username = f"@{u[1]}" if u[1] else "—"
    uid = u[0]
    balance = u[3]
    spent = u[4]
    return (
        f"🪪 ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ\n"
        f"┌ 👤 Имя: {name}\n"
        f"├ 🤖 Юзернейм: {username}\n"
        f"└ ⭐️ ID: {uid}\n"
        f"┌ 👛 Баланс: {balance:.2f}$\n"
        f"└ 📈 Потрачено всего: {spent:.2f}$"
    )


def text_topup(amount=None):
    base = (
        "💎 Пополнение через CryptoBot\n"
        "Введите сумму или выберите:\n"
    )
    if amount:
        commission = round(amount * 0.03, 2)
        credited = round(amount - commission, 2)
        base += (
            f"\n┌ 💰 Вы вводите: {amount:.2f}$\n"
            f"├ 📊 Комиссия CryptoBot (3%): {commission:.2f}$\n"
            f"└ ✅ Зачислится: {credited:.2f}$"
        )
    return base


def text_support():
    return (
        f"🎧 ТЕХПОДДЕРЖКА GAFTES\n"
        f"По всем вопросам пишите:\n"
        f"👉 {SUPPORT_USERNAME}\n"
        f"👉 {SUPPORT_LINK}"
    )


def text_market():
    groups = get_all_products_grouped()
    if not groups:
        return "🏪 МАРКЕТ GAFTES\n\nТоваров пока нет."
    g = groups[0]
    u_balance = None
    return g  # вернём объект, отрендерим снаружи


def text_market_render(user_id, group, qty=1):
    u = get_user(user_id)
    balance = u[3] if u else 0.0
    name = group["name"]
    price = group["price"]
    return (
        f"🏪 МАРКЕТ GAFTES\n"
        f"┌ 📲 {name}\n"
        f"│\n"
        f"│ 💵 Баланс: ${balance:.2f}\n"
        f"│ 💵 Цена: ${price:.2f}\n"
        f"└ Введите количество: {qty}"
    )


def text_my_purchases(user_id):
    purchases = get_user_purchases(user_id)
    if not purchases:
        return "📦 МОИ ПОКУПКИ\n\nПокупок пока нет."

    # группируем по названию
    from collections import defaultdict
    groups = defaultdict(list)
    totals = defaultdict(float)
    for item, name, amount, date in purchases:
        groups[name].append(item)
        totals[name] += amount

    text = "📦 МОИ ПОКУПКИ\n"
    for name, items in groups.items():
        text += f"┌ 📲 {name}\n"
        for it in items:
            text += f"│ {it}\n"
        text += f"└ 💰 Потрачено: ${totals[name]:.2f}\n\n"
    return text.strip()


def text_admin_panel():
    status = get_setting("status")
    price = get_setting("price")
    return (
        f"⚙️ АДМИН-ПАНЕЛЬ GAFTES\n"
        f"┌ 👑 Админ: {ADMIN_USERNAME}\n"
        f"├ {'🟢' if status == 'WORK' else '🔴'} Статус: {status}\n"
        f"└ 💰 Ценник: {price}$"
    )


def text_bans():
    banned = get_banned_users()
    text = "🚫 БАНЫ\n"
    if not banned:
        text += "Забаненных пользователей нет.\n"
    else:
        text += "Забаненные пользователи:\n"
        for uid, username, ban_date, ban_reason in banned:
            uname = f"@{username}" if username else str(uid)
            text += (
                f"┌ 👤 {uname}\n"
                f"├ ID: {uid}\n"
                f"├ 📅 Забанен: {ban_date}\n"
                f"└ 📝 Причина: {ban_reason}\n\n"
            )
    return text.strip()


def text_edit_product():
    groups = get_all_products_grouped()
    text = "🛠 РЕДАКЦИЯ ТОВАРА\nТекущие товары:\n"
    if not groups:
        text += "Товаров нет."
    else:
        for g in groups:
            text += f"┌ 📲 {g['name']}\n│ 💰 Цена: ${g['price']:.2f}\n│\n"
            for pid, item in g["items"]:
                text += f"│ {item}\n"
            text += "└\n"
    return text.strip()


def text_stats():
    users_count, sales_count, total_revenue, today_revenue = get_stats()
    status = get_setting("status")
    return (
        f"📊 СТАТИСТИКА\n"
        f"┌ 👥 Пользователей: {users_count}\n"
        f"├ 🛒 Продаж: {sales_count}\n"
        f"├ 💰 Оборот: ${total_revenue:.2f}\n"
        f"├ {'🟢' if status == 'WORK' else '🔴'} {status}\n"
        f"└ 📅 Сегодня: +${today_revenue:.2f}"
    )


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
    uid = call.from_user.id
    cid = call.message.chat.id
    mid = call.message.message_id
    data = call.data

    if is_banned(uid) and data != "back_main":
        bot.answer_callback_query(call.id, "🚫 Вы заблокированы.")
        return

    # ---- ГЛАВНОЕ МЕНЮ ----
    if data == "back_main":
        bot.edit_message_text(text_start(), cid, mid, reply_markup=kb_main())

    elif data == "profile":
        bot.edit_message_text(text_profile(uid), cid, mid, reply_markup=kb_profile())

    elif data == "support":
        bot.edit_message_text(text_support(), cid, mid, reply_markup=kb_support())

    elif data == "market":
        groups = get_all_products_grouped()
        if not groups:
            bot.edit_message_text("🏪 МАРКЕТ GAFTES\n\nТоваров пока нет.", cid, mid,
                                  reply_markup=types.InlineKeyboardMarkup().add(
                                      types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main")))
        else:
            g = groups[0]
            bot.edit_message_text(text_market_render(uid, g), cid, mid, reply_markup=kb_market(g))

    # ---- ПРОФИЛЬ ----
    elif data == "back_profile":
        bot.edit_message_text(text_profile(uid), cid, mid, reply_markup=kb_profile())

    # ---- ПОПОЛНЕНИЕ ----
    elif data == "topup":
        bot.edit_message_text(text_topup(), cid, mid, reply_markup=kb_topup())

    elif data in ("topup_5", "topup_10", "topup_25", "topup_50"):
        amount = float(data.split("_")[1])
        # Симуляция пополнения (без реального CryptoBot)
        bot.answer_callback_query(call.id, "💳 Создаём инвойс CryptoBot...")
        commission = round(amount * 0.03, 2)
        credited = round(amount - commission, 2)
        # В реальном боте тут создаётся инвойс через CryptoBot API
        # Для демо сразу зачисляем
        update_balance(uid, credited)
        bot.edit_message_text(
            f"✅ Баланс пополнен!\n"
            f"┌ 💰 Введено: {amount:.2f}$\n"
            f"├ 📊 Комиссия (3%): {commission:.2f}$\n"
            f"└ ✅ Зачислено: {credited:.2f}$",
            cid, mid,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️ Назад", callback_data="back_profile"))
        )

    elif data == "topup_custom":
        user_states[uid] = "awaiting_topup_amount"
        bot.edit_message_text(
            "💵 Введите сумму для пополнения (например: 15):",
            cid, mid,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("❌ Отмена", callback_data="topup"))
        )

    # ---- ПОКУПКА ----
    elif data.startswith("buy_"):
        parts = data.split("_")
        qty = int(parts[-1])
        name = "_".join(parts[1:-1])

        groups = get_all_products_grouped()
        group = next((g for g in groups if g["name"] == name), None)
        if not group:
            bot.answer_callback_query(call.id, "Товар не найден.")
            return

        price = group["price"]
        total = price * qty
        u = get_user(uid)
        if u[3] < total:
            bot.answer_callback_query(call.id, f"❌ Недостаточно средств. Нужно ${total:.2f}")
            return
        if len(group["items"]) < qty:
            bot.answer_callback_query(call.id, "❌ Недостаточно товаров в наличии.")
            return

        # Берём нужное кол-во товаров
        items_to_sell = group["items"][:qty]
        bought_items = []
        conn = sqlite3.connect("gaftes.db")
        c = conn.cursor()
        for pid, item in items_to_sell:
            c.execute("UPDATE products SET sold=1 WHERE id=?", (pid,))
            c.execute(
                "INSERT INTO purchases (user_id, product_id, item, amount, date) VALUES (?,?,?,?,?)",
                (uid, pid, item, price, datetime.datetime.now().isoformat())
            )
            bought_items.append(item)
        conn.commit()
        conn.close()
        deduct_balance(uid, total)

        items_text = "\n".join(bought_items)
        bot.edit_message_text(
            f"✅ ПОКУПКА УСПЕШНА!\n"
            f"🗃 Товар: {name}\n"
            f"💰 Списано: ${total:.2f}\n"
            f"📲 Ваш товар:\n{items_text}",
            cid, mid,
            reply_markup=kb_after_purchase()
        )

    elif data == "my_purchases":
        bot.edit_message_text(text_my_purchases(uid), cid, mid, reply_markup=kb_my_purchases())

    # ---- АДМИН-ПАНЕЛЬ ----
    elif data == "admin_panel":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "⛔️")
            return
        user_states.pop(uid, None)
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
            "🚫 Введите ID или @username пользователя для бана\n(и причину через | )\nПример: 123456789 | Спам",
            cid, mid, reply_markup=kb_cancel()
        )

    elif data == "admin_unban":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_unban_id"
        bot.edit_message_text(
            "✅ Введите ID пользователя для разбана:",
            cid, mid, reply_markup=kb_cancel()
        )

    elif data == "admin_broadcast":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_broadcast"
        bot.edit_message_text(
            "📢 РАССЫЛКА\nСообщение будет отправлено всем пользователям.\nВведите текст рассылки:",
            cid, mid, reply_markup=kb_cancel()
        )

    elif data == "admin_add_product":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_new_product"
        bot.edit_message_text(
            "➕ ДОБАВЛЕНИЕ ТОВАРА\nНапишите каждый товар с новой строки:\nформат: название | товар\n\nПример:\n7996 | лолкелдв\n1234 | другой товар\n5678 | ещё товар",
            cid, mid, reply_markup=kb_save_cancel()
        )

    elif data == "admin_save_product":
        if uid != ADMIN_ID:
            return
        state = user_states.get(uid)
        if state != "awaiting_new_product":
            bot.answer_callback_query(call.id, "Сначала введите данные товара.")
            return
        # Данные уже сохранены в тексте сообщения — просто сообщаем
        bot.answer_callback_query(call.id, "Введите товары текстом в чат, затем нажмите Сохранить.")

    elif data == "admin_edit_product":
        if uid != ADMIN_ID:
            return
        bot.edit_message_text(text_edit_product(), cid, mid, reply_markup=kb_admin_edit())

    elif data == "admin_change_price":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_new_price"
        bot.edit_message_text(
            "✏️ Введите новую цену для товара (например: MAX TOKEN | 7.50):",
            cid, mid, reply_markup=kb_cancel()
        )

    elif data == "admin_change_name":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_new_name"
        bot.edit_message_text(
            "📝 Введите: старое_название | новое_название\nПример: MAX TOKEN | PREMIUM TOKEN",
            cid, mid, reply_markup=kb_cancel()
        )

    elif data == "admin_delete_product":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_delete_product"
        bot.edit_message_text(
            "❌ Введите название товара для удаления:",
            cid, mid, reply_markup=kb_cancel()
        )

    elif data == "admin_topup_user":
        if uid != ADMIN_ID:
            return
        user_states[uid] = "awaiting_topup_user"
        bot.edit_message_text(
            "💳 Введите: ID_пользователя | сумма\nПример: 123456789 | 10.00",
            cid, mid, reply_markup=kb_cancel()
        )

    bot.answer_callback_query(call.id)


# ===================== ТЕКСТОВЫЕ СООБЩЕНИЯ (состояния) =====================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def on_text(msg):
    uid = msg.from_user.id
    text = msg.text.strip()
    state = user_states.get(uid)

    if is_banned(uid):
        bot.send_message(msg.chat.id, "🚫 Вы заблокированы.")
        return

    # --- Пополнение своя сумма ---
    if state == "awaiting_topup_amount":
        try:
            amount = float(text.replace(",", "."))
            if amount <= 0:
                raise ValueError
            commission = round(amount * 0.03, 2)
            credited = round(amount - commission, 2)
            # Симуляция зачисления
            update_balance(uid, credited)
            user_states.pop(uid, None)
            bot.send_message(
                msg.chat.id,
                f"✅ Баланс пополнен!\n"
                f"┌ 💰 Введено: {amount:.2f}$\n"
                f"├ 📊 Комиссия (3%): {commission:.2f}$\n"
                f"└ ✅ Зачислено: {credited:.2f}$",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("⬅️ Профиль", callback_data="profile"))
            )
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Введите корректную сумму (число).")

    # --- Рассылка ---
    elif state == "awaiting_broadcast" and uid == ADMIN_ID:
        all_users = get_all_users()
        sent = 0
        failed = 0
        for target_id in all_users:
            try:
                bot.send_message(target_id, f"📢 Сообщение от GAFTES:\n\n{text}")
                sent += 1
            except Exception:
                failed += 1
        user_states.pop(uid, None)
        bot.send_message(
            msg.chat.id,
            f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
        )

    # --- Добавление товара ---
    elif state == "awaiting_new_product" and uid == ADMIN_ID:
        lines = [l.strip() for l in text.split("\n") if "|" in l]
        if not lines:
            bot.send_message(msg.chat.id, "❌ Неверный формат. Пример:\nMAX TOKEN | 7996 | лолкелдв")
            return
        conn = sqlite3.connect("gaftes.db")
        c = conn.cursor()
        added = 0
        for line in lines:
            parts = [p.strip() for p in line.split("|", 1)]
            if len(parts) == 2:
                name, item = parts
                # Берём цену из настроек
                price = float(get_setting("price") or 5.0)
                c.execute("INSERT INTO products (name, price, item) VALUES (?,?,?)", (name, price, item))
                added += 1
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        bot.send_message(
            msg.chat.id,
            f"✅ Добавлено товаров: {added}",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
        )

    # --- Изменить цену ---
    elif state == "awaiting_new_price" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) == 2:
            name, price_str = parts
            try:
                new_price = float(price_str.replace(",", ".").replace("$", ""))
                conn = sqlite3.connect("gaftes.db")
                c = conn.cursor()
                c.execute("UPDATE products SET price=? WHERE name=?", (new_price, name))
                conn.commit()
                conn.close()
                user_states.pop(uid, None)
                bot.send_message(
                    msg.chat.id,
                    f"✅ Цена товара «{name}» изменена на ${new_price:.2f}",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
                )
            except ValueError:
                bot.send_message(msg.chat.id, "❌ Неверная цена.")
        else:
            bot.send_message(msg.chat.id, "❌ Формат: Название | цена")

    # --- Изменить название ---
    elif state == "awaiting_new_name" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) == 2:
            old_name, new_name = parts
            conn = sqlite3.connect("gaftes.db")
            c = conn.cursor()
            c.execute("UPDATE products SET name=? WHERE name=?", (new_name, old_name))
            conn.commit()
            conn.close()
            user_states.pop(uid, None)
            bot.send_message(
                msg.chat.id,
                f"✅ Название изменено: «{old_name}» → «{new_name}»",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            )
        else:
            bot.send_message(msg.chat.id, "❌ Формат: старое | новое")

    # --- Удалить товар ---
    elif state == "awaiting_delete_product" and uid == ADMIN_ID:
        conn = sqlite3.connect("gaftes.db")
        c = conn.cursor()
        c.execute("DELETE FROM products WHERE name=? AND sold=0", (text,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        bot.send_message(
            msg.chat.id,
            f"✅ Удалено {deleted} единиц товара «{text}»",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
        )

    # --- Бан ---
    elif state == "awaiting_ban_id" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        target_input = parts[0]
        reason = parts[1] if len(parts) > 1 else "Нарушение правил"
        try:
            target_id = int(target_input)
        except ValueError:
            # пытаемся найти по username
            uname = target_input.lstrip("@")
            conn = sqlite3.connect("gaftes.db")
            c = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE username=?", (uname,))
            row = c.fetchone()
            conn.close()
            if not row:
                bot.send_message(msg.chat.id, "❌ Пользователь не найден.")
                return
            target_id = row[0]
        ban_user(target_id, reason)
        user_states.pop(uid, None)
        bot.send_message(
            msg.chat.id,
            f"🚫 Пользователь {target_id} забанен.\nПричина: {reason}",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
        )

    # --- Разбан ---
    elif state == "awaiting_unban_id" and uid == ADMIN_ID:
        try:
            target_id = int(text)
            unban_user(target_id)
            user_states.pop(uid, None)
            bot.send_message(
                msg.chat.id,
                f"✅ Пользователь {target_id} разбанен.",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            )
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Введите числовой ID.")

    # --- Пополнение баланса пользователя (админ) ---
    elif state == "awaiting_topup_user" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) == 2:
            try:
                target_id = int(parts[0])
                amount = float(parts[1].replace(",", ".").replace("$", ""))
                update_balance(target_id, amount)
                user_states.pop(uid, None)
                bot.send_message(
                    msg.chat.id,
                    f"✅ Баланс пользователя {target_id} пополнен на ${amount:.2f}",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
                )
                try:
                    bot.send_message(target_id, f"💳 Ваш баланс пополнен на ${amount:.2f} администратором.")
                except Exception:
                    pass
            except ValueError:
                bot.send_message(msg.chat.id, "❌ Неверный формат.")
        else:
            bot.send_message(msg.chat.id, "❌ Формат: ID | сумма")

    else:
        # Нет активного состояния — показываем старт
        bot.send_message(msg.chat.id, text_start(), reply_markup=kb_main())


# ===================== ЗАПУСК =====================
if __name__ == "__main__":
    init_db()
    print("✅ GAFTES Bot запущен...")
    bot.infinity_polling(skip_pending=True)
