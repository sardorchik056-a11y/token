import telebot
from telebot import types
import json
import os
from datetime import datetime
import requests
import time
import threading

# ==================== КОНФИГ ====================
BOT_TOKEN = "8796598287:AAFK9lvJ_T3oVC4Xr3VH0U_ArmPmY4CskSs"
ADMIN_IDS = [8118184388]
CRYPTOBOT_TOKEN = "582363:AALEf7JOugnrQyrkMHzH5UrO7pdOjjYnTQy"
SUPPORT_LINK = "https://t.me/your_admin_username"  # <-- замени на юз поддержки
DB_FILE = "users_db.json"
ADMIN_DB = "admin_db.json"
INVOICE_DB = "invoices_db.json"

# ==================== КАСТОМНЫЕ ЭМОДЗИ ====================
# Замени значения на свои ID кастомных эмодзи
E = {
    "shop":    "5307843983102204243",   # 🏪
    "buy":     "5307843983102204243",   # 🔑
    "balance": "6078158956188930337",   # 🔵
    "rules":   "5341715473882955310",   # ⚙️
    "support": "5848400681416793625",   # 🧡
    "token":   "5449407131675558756",   # 💎
    "back":    "6039539366177541657",   # 🔙
    "confirm": "5206607081334906820",   # ✅
    "cancel":  "5210952531676504517",   # ❌
    "refill":  "6078158956188930337",   # 💰
    "channel": "5271604874419647061",   # 🔗
    "check":   "5206607081334906820",   # ✅
    "pay":     "6078158956188930337",   # 💳
    "price":   "5197434882321567830",   # 💵
    "user":    "5906581476639513176",   # 👤
    "id":      "5445353829304387411",   # 🪪
}

def e(key):
    """Возвращает кастомный эмодзи тег для текста сообщений"""
    return f"<tg-emoji emoji-id=\"{E[key]}\">⭐</tg-emoji>"

def eb(key, label, **kwargs):
    """InlineKeyboardButton с кастомным эмодзи через icon_custom_emoji_id"""
    return types.InlineKeyboardButton(
        text=label,
        icon_custom_emoji_id=E[key],
        **kwargs
    )

# ==================== БД ====================
def load_users():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(DB_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_admin_db():
    if os.path.exists(ADMIN_DB):
        with open(ADMIN_DB, 'r') as f:
            return json.load(f)
    return {
        "banned_users": [],
        "product_price": 5,
        "min_purchase": 3,
        "tokens_in_bot": 1488,
        "content": [],
        "channels": [],
        "menu_sticker": None
    }

def save_admin_db(data):
    with open(ADMIN_DB, 'w') as f:
        json.dump(data, f, indent=2)

def load_invoices():
    if os.path.exists(INVOICE_DB):
        with open(INVOICE_DB, 'r') as f:
            return json.load(f)
    return {}

def save_invoices(invoices):
    with open(INVOICE_DB, 'w') as f:
        json.dump(invoices, f, indent=2)

def check_bot_admin_in_channel(channel_id):
    try:
        chat_member = bot.get_chat_member(channel_id, bot.get_me().id)
        return chat_member.status in ['administrator', 'creator']
    except Exception as e:
        print(f"Ошибка проверки админа: {str(e)}")
        return False

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== CRYPTOBOT ====================
def create_invoice(amount_usd, user_id, description="Пополнение баланса"):
    try:
        headers = {
            "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
            "Content-Type": "application/json"
        }
        payload = {
            "asset": "USDT",
            "amount": str(amount_usd),
            "currency_code": "USD",
            "description": description,
            "expires_in": 3600
        }
        response = requests.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers=headers,
            json=payload
        )
        result = response.json()
        if result.get("ok"):
            invoice = result.get("result")
            return {
                "invoice_id": invoice.get("invoice_id"),
                "pay_url": invoice.get("pay_url"),
                "amount": amount_usd,
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "paid": False
            }
        else:
            print(f"CryptoBot ошибка: {result}")
            return None
    except Exception as e:
        print(f"Ошибка создания инвойса: {str(e)}")
        return None

def check_invoice_status(invoice_id):
    try:
        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
        response = requests.get(
            f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}",
            headers=headers
        )
        result = response.json()
        if result.get("ok"):
            invoices = result.get("result", {}).get("items", [])
            if invoices:
                inv = invoices[0]
                return {
                    "status": inv.get("status"),
                    "amount": inv.get("amount"),
                    "paid_amount": inv.get("paid_amount")
                }
        return None
    except Exception as e:
        print(f"Ошибка проверки инвойса: {str(e)}")
        return None

def monitor_invoice(invoice_id, user_id, chat_id, message_id, amount_usd):
    max_checks = 1800
    check_count = 0
    while check_count < max_checks:
        time.sleep(2)
        check_count += 1
        status_info = check_invoice_status(invoice_id)
        if not status_info:
            continue
        if status_info["status"] == "paid":
            users = load_users()
            if str(user_id) in users:
                users[str(user_id)]["balance"] = round(users[str(user_id)]["balance"] + amount_usd, 2)
                save_users(users)
            invoices = load_invoices()
            if invoice_id in invoices:
                invoices[invoice_id]["paid"] = True
                save_invoices(invoices)
            try:
                bot.edit_message_text(
                    f"Платеж успешно получен!\n\nВыплачено: {amount_usd}$\nБаланс пополнен на {amount_usd}$",
                    chat_id, message_id
                , parse_mode="HTML")
            except:
                pass
            time.sleep(3)
            try:
                bot.delete_message(chat_id, message_id)
                show_main_menu(chat_id, user_id)
            except:
                pass
            break
        elif status_info["status"] == "expired":
            try:
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(eb("back", "Назад", callback_data="check_balance"))
                bot.edit_message_text(
                    "Инвойс истек! Время для оплаты истекло.",
                    chat_id, message_id, reply_markup=markup
                , parse_mode="HTML")
            except:
                pass
            break

# ==================== ХЕЛПЕРЫ ====================
def is_user_banned(user_id):
    admin_db = load_admin_db()
    return str(user_id) in admin_db["banned_users"]

def is_admin(user_id):
    return user_id in ADMIN_IDS

def resolve_channel_id(channel_input):
    channel_input = channel_input.strip()
    if "t.me/" in channel_input:
        username = channel_input.split("t.me/")[-1].strip("/").strip()
        username = username.split("?")[0].split("/")[0]
        return f"@{username}"
    if channel_input.startswith("@"):
        return channel_input
    try:
        return int(channel_input)
    except ValueError:
        return None

def get_channel_invite_url(channel_id):
    if isinstance(channel_id, str) and channel_id.startswith("@"):
        return f"https://t.me/{channel_id[1:]}"
    elif isinstance(channel_id, int):
        return f"https://t.me/c/{str(channel_id).replace('-100', '')}"
    return None

def is_subscribed_to_all(user_id):
    admin_db = load_admin_db()
    channels = admin_db.get("channels", [])
    if not channels:
        return True
    for channel_id in channels:
        try:
            chat_member = bot.get_chat_member(channel_id, user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def register_user(user):
    users = load_users()
    user_id = user.id
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": user.username or "Unknown",
            "id": user_id,
            "balance": 0,
            "joined": datetime.now().isoformat()
        }
        save_users(users)

def send_subscription_message(chat_id):
    admin_db = load_admin_db()
    channels = admin_db.get("channels", [])

    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, channel in enumerate(channels, 1):
        url = get_channel_invite_url(channel)
        if url:
            markup.add(eb("channel", f"{i} Канал", url=url))
    markup.add(eb("check", "Подписался", callback_data="check_subscription"))

    bot.send_message(
        chat_id,
        '<b><tg-emoji emoji-id=\"5420323339723881652">⭐</tg-emoji>Для доступа в бот нужно подписаться на канал\n\nПосле подписки нажми кнопку Подписался<tg-emoji emoji-id=\"5206607081334906820">⭐</tg-emoji></b>',
        reply_markup=markup
    , parse_mode="HTML")

# ==================== /getfileid ====================
@bot.message_handler(commands=['getfileid'])
def getfileid_cmd(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "Нет доступа!", parse_mode="HTML")
        return
    msg = bot.send_message(message.chat.id, "Кинь стикер который будет показываться перед меню:", parse_mode="HTML")
    bot.register_next_step_handler(msg, save_sticker_file_id)

def save_sticker_file_id(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    if not message.sticker:
        bot.send_message(message.chat.id, "Это не стикер! Попробуй ещё раз — /getfileid", parse_mode="HTML")
        return
    file_id = message.sticker.file_id
    admin_db = load_admin_db()
    admin_db["menu_sticker"] = file_id
    save_admin_db(admin_db)
    bot.send_message(message.chat.id, f"Стикер сохранён!\nfile_id: {file_id}\n\nТеперь он будет показываться перед главным меню.", parse_mode="HTML")

# ==================== ГЛАВНОЕ МЕНЮ ====================
def show_main_menu(chat_id, user_id, message_id=None):
    users = load_users()
    user = users.get(str(user_id), {})
    balance = user.get("balance", 0)
    username = user.get("username", "Unknown")

    text = (
        "<b>Kretros Shop</b>\n"
        "——————————————\n"
        f'|<b><tg-emoji emoji-id=\"5906581476639513176">⭐</tg-emoji>User: @{username}!\n'
        f'|<tg-emoji emoji-id=\"5445353829304387411">⭐</tg-emoji>ID: {user_id}\n'
        f'|<tg-emoji emoji-id=\"6078158956188930337">⭐</tg-emoji>Баланс: {balance}$</b>\n'
        "——————————————"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        eb("buy", "Купить Token", callback_data="buy_token")
    )
    markup.add(
        eb("balance", "Баланс", callback_data="check_balance"),
        eb("rules", "Правила", callback_data="rules")
    )
    markup.add(
        eb("support", "Поддержка", url=SUPPORT_LINK)
    )

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="HTML")
    else:
        admin_db = load_admin_db()
        sticker_id = admin_db.get('menu_sticker')
        if sticker_id:
            try:
                bot.send_sticker(chat_id, sticker_id)
            except:
                pass
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

# ==================== /start ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if is_user_banned(user_id):
        return

    if not is_subscribed_to_all(user_id):
        send_subscription_message(message.chat.id)
        return

    register_user(message.from_user)
    show_main_menu(message.chat.id, user_id)

# ==================== ПРОВЕРКА ПОДПИСКИ ====================
@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    if is_subscribed_to_all(user_id):
        register_user(call.from_user)
        show_main_menu(call.message.chat.id, user_id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Сначала подпишись на ВСЕ каналы!", show_alert=True)

# ==================== КУПИТЬ ТОКЕН ====================
@bot.callback_query_handler(func=lambda call: call.data == "buy_token")
def buy_token(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    if not is_subscribed_to_all(user_id):
        bot.answer_callback_query(call.id, "Сначала подпишись на канал!", show_alert=True)
        send_subscription_message(call.message.chat.id)
        return

    admin_db = load_admin_db()
    price = admin_db["product_price"]
    min_purchase = admin_db["min_purchase"]
    tokens_left = admin_db["tokens_in_bot"]

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(eb("back", "Назад", callback_data="back_to_menu"))

    msg = bot.edit_message_text(
        f'<tg-emoji emoji-id=\"5449407131675558756">⭐</tg-emoji><b>TOKEN</b>\n'
        f"——————————————\n"
        f'<b>Ценник: {price}<tg-emoji emoji-id=\"5197434882321567830">⭐</tg-emoji>\n'
        f'Мин покупка: {min_purchase} шт<tg-emoji emoji-id=\"5397916757333654639">⭐</tg-emoji>\n'
        f'Кол-во в боте: {tokens_left} шт<tg-emoji emoji-id=\"5386367538735104399">⭐</tg-emoji></b>\n'
        f"——————————————\n\n"
        f'<b>Введите количество токенов:</b>',
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    , parse_mode="HTML")

    bot.register_next_step_handler(msg, process_quantity, call.message.message_id)

# ==================== ВВОД КОЛИЧЕСТВА ====================
def process_quantity(message, msg_id):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if is_user_banned(user_id):
        return

    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass

    admin_db = load_admin_db()

    # Проверяем что юзер не написал что-то странное
    text = message.text.strip() if message.text else ""

    try:
        quantity = int(text)
    except ValueError:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(eb("back", "Назад", callback_data="back_to_menu"))
        msg = bot.edit_message_text(
            f'<tg-emoji emoji-id=\"5449407131675558756">⭐</tg-emoji><b>TOKEN</b>\n'
            f"——————————————\n"
            f'<b>Ценник: {price}<tg-emoji emoji-id=\"5197434882321567830">⭐</tg-emoji>\n'
            f'Мин покупка: {min_purchase} шт<tg-emoji emoji-id=\"5397916757333654639">⭐</tg-emoji>\n'
            f'Кол-во в боте: {tokens_left} шт<tg-emoji emoji-id=\"5386367538735104399">⭐</tg-emoji></b>\n'
            f"——————————————\n\n"
            f'<b>Введите число!</b>',
            chat_id, msg_id, reply_markup=markup
        , parse_mode="HTML")
        bot.register_next_step_handler(msg, process_quantity, msg_id)
        return

    min_purchase = admin_db["min_purchase"]
    price = admin_db["product_price"]
    tokens_left = admin_db["tokens_in_bot"]

    if quantity < min_purchase:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(eb("back", "Назад", callback_data="back_to_menu"))
        msg = bot.edit_message_text(
            f'<tg-emoji emoji-id=\"5449407131675558756">⭐</tg-emoji><b>TOKEN</b>\n'
            f"——————————————\n"
            f'<b>Ценник: {price}<tg-emoji emoji-id=\"5197434882321567830">⭐</tg-emoji>\n'
            f'Мин покупка: {min_purchase} шт<tg-emoji emoji-id=\"5397916757333654639">⭐</tg-emoji>\n'
            f'Кол-во в боте: {tokens_left} шт<tg-emoji emoji-id=\"5386367538735104399">⭐</tg-emoji></b>\n'
            f"——————————————\n\n"
            f'<b>Минимум {min_purchase}!</b>',
            chat_id, msg_id, reply_markup=markup
        , parse_mode="HTML")
        bot.register_next_step_handler(msg, process_quantity, msg_id)
        return

    if quantity > tokens_left:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(eb("back", "Назад", callback_data="back_to_menu"))
        msg = bot.edit_message_text(
            f'<tg-emoji emoji-id=\"5449407131675558756">⭐</tg-emoji><b>TOKEN</b>\n'
            f"——————————————\n"
            f'<b>Ценник: {price}<tg-emoji emoji-id=\"5197434882321567830">⭐</tg-emoji>\n'
            f'Мин покупка: {min_purchase} шт<tg-emoji emoji-id=\"5397916757333654639">⭐</tg-emoji>\n'
            f'Кол-во в боте: {tokens_left} шт<tg-emoji emoji-id=\"5386367538735104399">⭐</tg-emoji></b>\n'
            f"——————————————\n\n"
            f'<b>Недостаточно токенов!</b>',
            chat_id, msg_id, reply_markup=markup
        , parse_mode="HTML")
        bot.register_next_step_handler(msg, process_quantity, msg_id)
        return

    total_price = round(quantity * price, 2)
    users = load_users()
    user_balance = users.get(str(user_id), {}).get("balance", 0)

    # Экран подтверждения
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        eb("confirm", "Купить", callback_data=f"confirm_buy_{quantity}"),
        eb("cancel", "Отмена", callback_data="buy_token")
    )

    bot.edit_message_text(
        f'<tg-emoji emoji-id=\"5206607081334906820">⭐</tg-emoji><b>Подтверждение!</b>\n'
        f"——————————————\n"
        f'<b><tg-emoji emoji-id=\"5226513232549664618">⭐</tg-emoji>Количество: {quantity} шт\n'
        f'<tg-emoji emoji-id=\"5197434882321567830">⭐</tg-emoji>Цена за шт: {price}$\n'
        f'<tg-emoji emoji-id=\"5201691993775818138">⭐</tg-emoji>Итого: {total_price}$\n'
        f'<tg-emoji emoji-id=\"6078158956188930337">⭐</tg-emoji>баланс: {user_balance}$</b>\n'
        f"——————————————",
        chat_id, msg_id, reply_markup=markup
    , parse_mode="HTML")

# ==================== ПОДТВЕРЖДЕНИЕ ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_buy_"))
def confirm_buy(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if is_user_banned(user_id):
        return

    quantity = int(call.data.split("_")[2])
    admin_db = load_admin_db()
    price = admin_db["product_price"]
    tokens_left = admin_db["tokens_in_bot"]
    min_purchase = admin_db["min_purchase"]
    total_price = round(quantity * price, 2)

    users = load_users()
    user_balance = users.get(str(user_id), {}).get("balance", 0)

    if quantity < min_purchase or quantity > tokens_left:
        bot.answer_callback_query(call.id, "Данные изменились, попробуй заново!", show_alert=True)
        show_main_menu(chat_id, user_id, msg_id)
        return

    if user_balance < total_price:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            eb("refill", "Пополнить баланс", callback_data="refill_balance"),
            eb("cancel", "Отмена", callback_data="back_to_menu")
        )
        bot.edit_message_text(
            f'<b><tg-emoji emoji-id=\"5210952531676504517">⭐</tg-emoji>Недостаточно средств!\n\n<tg-emoji emoji-id=\"5449683594425410231">⭐</tg-emoji>Нужно: {total_price}$\n<tg-emoji emoji-id=\"6078158956188930337">⭐</tg-emoji>У вас: {user_balance}$</b>',
            chat_id, msg_id, reply_markup=markup
        , parse_mode="HTML")
        return

    # Проверяем наличие контента
    content_list = admin_db.get("content", [])
    if isinstance(content_list, str):
        content_list = [content_list] if content_list.strip() else []

    if len(content_list) < quantity:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            eb("back", "Назад", callback_data="back_to_menu")
        )
        bot.edit_message_text(
            f"<b>Ошибка! Контент закончился.\n\nОбратитесь в поддержку.</b>",
            chat_id, msg_id, reply_markup=markup
        , parse_mode="HTML")
        return

    # Списываем
    users[str(user_id)]["balance"] = round(users[str(user_id)]["balance"] - total_price, 2)
    save_users(users)
    admin_db["tokens_in_bot"] -= quantity

    # Берём нужное количество строк контента и удаляем их из списка
    issued_content = content_list[:quantity]
    admin_db["content"] = content_list[quantity:]
    save_admin_db(admin_db)

    content_text = "\n".join(issued_content)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(eb("back", "Главное меню", callback_data="back_to_menu"))

    bot.edit_message_text(
        f'<tg-emoji emoji-id=\"5206607081334906820">⭐</tg-emoji>Покупка успешна!\n'
        f"——————————————\n"
        f'<tg-emoji emoji-id=\"5307843983102204243">⭐</tg-emoji>Куплено: {quantity} шт\n'
        f'<tg-emoji emoji-id=\"6078158956188930337">⭐</tg-emoji>Потрачено: {total_price}$\n'
        f"——————————————\n\n"
        f"{content_text}",
        chat_id, msg_id, reply_markup=markup
    , parse_mode="HTML")

# ==================== БАЛАНС ====================
@bot.callback_query_handler(func=lambda call: call.data == "check_balance")
def check_balance(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    users = load_users()
    user = users.get(str(user_id), {})
    balance = user.get("balance", 0)
    username = user.get("username", "Unknown")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        eb("refill", "Пополнить баланс", callback_data="refill_balance"),
        eb("back", "Назад", callback_data="back_to_menu")
    )

    bot.edit_message_text(
        f"——————————————\n"
        f'|<tg-emoji emoji-id=\"5906581476639513176">⭐</tg-emoji>User: @{username}!\n'
        f'|<tg-emoji emoji-id=\"5445353829304387411">⭐</tg-emoji>ID: {user_id}\n'
        f'|<tg-emoji emoji-id=\"6078158956188930337">⭐</tg-emoji>Баланс: {balance}$\n'
        f"——————————————",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    , parse_mode="HTML")

# ==================== ПОПОЛНИТЬ БАЛАНС ====================
@bot.callback_query_handler(func=lambda call: call.data == "refill_balance")
def refill_balance(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    admin_db = load_admin_db()
    min_amount = admin_db.get("product_price", 5)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(eb("back", "Назад", callback_data="check_balance"))

    msg = bot.edit_message_text(
        f'<b><tg-emoji emoji-id=\"6078158956188930337">⭐</tg-emoji>Пополнение баланса\n\n<tg-emoji emoji-id=\"5307843983102204243">⭐</tg-emoji>Введите сумму от {min_amount}$:</b>',
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    , parse_mode="HTML")

    bot.register_next_step_handler(msg, process_refill, call.message.message_id)

def process_refill(message, msg_id):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if is_user_banned(user_id):
        return

    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass

    admin_db = load_admin_db()
    min_amount = admin_db.get("product_price", 5)

    text = message.text.strip() if message.text else ""

    try:
        amount = float(text)
    except ValueError:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(eb("back", "Назад", callback_data="check_balance"))
        msg = bot.edit_message_text(
            f"Пополнение баланса\n\nВведи число! Попробуй заново:",
            chat_id, msg_id, reply_markup=markup
        , parse_mode="HTML")
        bot.register_next_step_handler(msg, process_refill, msg_id)
        return

    if amount < min_amount:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(eb("back", "Назад", callback_data="check_balance"))
        msg = bot.edit_message_text(
            f'<b><tg-emoji emoji-id=\"6078158956188930337">⭐</tg-emoji>Пополнение баланса\n\nМинимум {min_amount}$! Введи заново:</b>',
            chat_id, msg_id, reply_markup=markup
        , parse_mode="HTML")
        bot.register_next_step_handler(msg, process_refill, msg_id)
        return

    invoice = create_invoice(amount, user_id)

    if not invoice:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(eb("back", "Назад", callback_data="check_balance"))
        bot.edit_message_text(
            "<b>Ошибка создания инвойса. Попробуй позже.<b>",
            chat_id, msg_id, reply_markup=markup
        , parse_mode="HTML")
        return

    invoices = load_invoices()
    invoices[invoice["invoice_id"]] = invoice
    save_invoices(invoices)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        eb("pay", "Оплатить", url=invoice['pay_url']),
        eb("back", "Назад", callback_data="check_balance")
    )

    msg = bot.edit_message_text(
        f'<tg-emoji emoji-id=\"6078158956188930337">⭐</tg-emoji><b>Счет на оплату\n\n<tg-emoji emoji-id=\"5224257782013769471">⭐</tg-emoji>Сумма: {amount}$\n<tg-emoji emoji-id=\"5307843983102204243">⭐</tg-emoji>Метод: CryptoBot (USDT)\n\nОжидаю оплату...</b>',
        chat_id, msg_id, reply_markup=markup
    , parse_mode="HTML")

    thread = threading.Thread(
        target=monitor_invoice,
        args=(invoice["invoice_id"], user_id, chat_id, msg.message_id, amount)
    )
    thread.daemon = True
    thread.start()

# ==================== ПРАВИЛА ====================
@bot.callback_query_handler(func=lambda call: call.data == "rules")
def rules(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(eb("back", "Назад", callback_data="back_to_menu"))

    bot.edit_message_text(
        '<tg-emoji emoji-id=\"5244961448525848230">⭐</tg-emoji>  Баланс с бота не выводится.\n\n'
        '<tg-emoji emoji-id=\"5242293676834579345">⭐</tg-emoji>  Гарантия на токены составляет 30 минут после покупки.\n\n'
        '<tg-emoji emoji-id=\"5242652525647127686">⭐</tg-emoji>  Любая попытка обмануть сервис равносильна блокировке.',
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    , parse_mode="HTML")

# ==================== НАЗАД В МЕНЮ ====================
@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return
    show_main_menu(call.message.chat.id, user_id, call.message.message_id)

# ==================== АДМИНКА ====================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "Нет доступа!", parse_mode="HTML")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Управление каналами", callback_data="admin_channels"),
        types.InlineKeyboardButton("Выдать баланс", callback_data="admin_give_balance"),
        types.InlineKeyboardButton("Бан/Анбан", callback_data="admin_ban"),
        types.InlineKeyboardButton("Изменить остаток", callback_data="admin_stock"),
        types.InlineKeyboardButton("Изменить цену", callback_data="admin_price"),
        types.InlineKeyboardButton("Мин количество", callback_data="admin_min_qty"),
        types.InlineKeyboardButton("Изменить контент", callback_data="admin_content")
    )

    bot.send_message(message.chat.id, "Админ Панель", reply_markup=markup, parse_mode="HTML")

# ==================== АДМИН: КАНАЛЫ ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_channels")
def admin_channels(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    admin_db = load_admin_db()
    channels = admin_db.get("channels", [])

    text = "Управление Каналами\n\n"
    if channels:
        for idx, ch_id in enumerate(channels, 1):
            text += f"{idx}. {ch_id}\n"
    else:
        text += "Каналы не добавлены\n"

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("Добавить канал", callback_data="admin_add_channel"))
    if channels:
        markup.add(types.InlineKeyboardButton("Удалить канал", callback_data="admin_remove_channel"))
    markup.add(types.InlineKeyboardButton("Назад", callback_data="admin_back"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_channel")
def admin_add_channel(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("Назад", callback_data="admin_channels"))

    msg = bot.edit_message_text(
        "Введи ID канала, @username или ссылку t.me/...",
        call.message.chat.id, call.message.message_id, reply_markup=markup
    , parse_mode="HTML")
    bot.register_next_step_handler(msg, process_add_channel)

def process_add_channel(message):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        return

    channel_input = message.text.strip()
    channel_id = resolve_channel_id(channel_input)

    if channel_id is None:
        bot.send_message(message.chat.id, "Неверный формат! Введи @username, ссылку t.me/... или числовой ID.", parse_mode="HTML")
        return

    if not check_bot_admin_in_channel(channel_id):
        bot.send_message(
            message.chat.id,
            f"Бот должен быть администратором в канале {channel_input}\n\nДобавь бота админом и попробуй снова!"
        , parse_mode="HTML")
        return

    admin_db = load_admin_db()
    channels = admin_db.get("channels", [])

    if channel_id not in channels:
        channels.append(channel_id)
        admin_db["channels"] = channels
        save_admin_db(admin_db)
        bot.send_message(message.chat.id, f"Канал {channel_input} добавлен!", parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "Канал уже в списке", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "admin_remove_channel")
def admin_remove_channel(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    admin_db = load_admin_db()
    channels = admin_db.get("channels", [])

    if not channels:
        bot.answer_callback_query(call.id, "Нет каналов для удаления!", show_alert=True)
        return

    text = "Выбери канал для удаления:\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    for idx, ch_id in enumerate(channels, 1):
        text += f"{idx}. {ch_id}\n"
        markup.add(types.InlineKeyboardButton(f"Удалить {ch_id}", callback_data=f"remove_ch_{idx-1}"))
    markup.add(types.InlineKeyboardButton("Назад", callback_data="admin_channels"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_ch_"))
def process_remove_channel(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    try:
        idx = int(call.data.split("_")[2])
        admin_db = load_admin_db()
        channels = admin_db.get("channels", [])

        if 0 <= idx < len(channels):
            removed = channels.pop(idx)
            admin_db["channels"] = channels
            save_admin_db(admin_db)
            bot.answer_callback_query(call.id, f"Канал {removed} удален!", show_alert=True)
            admin_channels(call)
        else:
            bot.answer_callback_query(call.id, "Ошибка индекса!", show_alert=True)
    except Exception as ex:
        bot.answer_callback_query(call.id, f"Ошибка: {str(ex)}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "admin_back")
def admin_back(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    admin_panel(call.message)

# ==================== АДМИН: БАЛАНС ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_give_balance")
def admin_give_balance(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return
    msg = bot.send_message(call.message.chat.id, "Введи ID пользователя:", parse_mode="HTML")
    bot.register_next_step_handler(msg, admin_get_user_id_for_balance)

def admin_get_user_id_for_balance(message):
    try:
        target_user_id = int(message.text)
        msg = bot.send_message(message.chat.id, "Введи сумму для выдачи:", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_process_balance, target_user_id)
    except ValueError:
        bot.send_message(message.chat.id, "ID должно быть числом!", parse_mode="HTML")

def admin_process_balance(message, target_user_id):
    try:
        amount = float(message.text)
        users = load_users()
        if str(target_user_id) not in users:
            users[str(target_user_id)] = {
                "username": "Unknown", "id": target_user_id,
                "balance": 0, "joined": datetime.now().isoformat()
            }
        users[str(target_user_id)]["balance"] = round(users[str(target_user_id)]["balance"] + amount, 2)
        save_users(users)
        bot.send_message(message.chat.id, f"Выдано {amount}$ пользователю {target_user_id}", parse_mode="HTML")
    except ValueError:
        bot.send_message(message.chat.id, "Введи число!", parse_mode="HTML")

# ==================== АДМИН: БАН ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_ban")
def admin_ban(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return
    msg = bot.send_message(call.message.chat.id, "Введи ID пользователя для бана/анбана:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_ban)

def process_ban(message):
    try:
        target_user_id = str(int(message.text))
        admin_db = load_admin_db()
        if target_user_id in admin_db["banned_users"]:
            admin_db["banned_users"].remove(target_user_id)
            bot.send_message(message.chat.id, f"Пользователь {target_user_id} разбанен", parse_mode="HTML")
        else:
            admin_db["banned_users"].append(target_user_id)
            bot.send_message(message.chat.id, f"Пользователь {target_user_id} забанен", parse_mode="HTML")
        save_admin_db(admin_db)
    except ValueError:
        bot.send_message(message.chat.id, "ID должно быть числом!", parse_mode="HTML")

# ==================== АДМИН: ОСТАТОК ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_stock")
def admin_stock(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return
    msg = bot.send_message(call.message.chat.id, "Введи новое количество токенов:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_stock)

def process_stock(message):
    try:
        quantity = int(message.text)
        admin_db = load_admin_db()
        admin_db["tokens_in_bot"] = quantity
        save_admin_db(admin_db)
        bot.send_message(message.chat.id, f"Остаток изменен на {quantity}", parse_mode="HTML")
    except ValueError:
        bot.send_message(message.chat.id, "Введи число!", parse_mode="HTML")

# ==================== АДМИН: ЦЕНА ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_price")
def admin_price(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return
    msg = bot.send_message(call.message.chat.id, "Введи новую цену токена:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_price)

def process_price(message):
    try:
        price = float(message.text)
        admin_db = load_admin_db()
        admin_db["product_price"] = price
        save_admin_db(admin_db)
        bot.send_message(message.chat.id, f"Цена изменена на {price}$", parse_mode="HTML")
    except ValueError:
        bot.send_message(message.chat.id, "Введи число!", parse_mode="HTML")

# ==================== АДМИН: МИН КОЛ-ВО ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_min_qty")
def admin_min_qty(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return
    msg = bot.send_message(call.message.chat.id, "Введи минимальное количество покупки:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_min_qty)

def process_min_qty(message):
    try:
        min_qty = int(message.text)
        admin_db = load_admin_db()
        admin_db["min_purchase"] = min_qty
        save_admin_db(admin_db)
        bot.send_message(message.chat.id, f"Минимум изменено на {min_qty}", parse_mode="HTML")
    except ValueError:
        bot.send_message(message.chat.id, "Введи число!", parse_mode="HTML")

# ==================== АДМИН: КОНТЕНТ ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_content")
def admin_content(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    admin_db = load_admin_db()
    content_list = admin_db.get("content", [])
    if isinstance(content_list, str):
        content_list = [content_list] if content_list.strip() else []

    count = len(content_list)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Добавить контент", callback_data="admin_content_add"),
        types.InlineKeyboardButton("Очистить весь контент", callback_data="admin_content_clear"),
        types.InlineKeyboardButton("Назад", callback_data="admin_back")
    )

    bot.edit_message_text(
        f"Управление контентом\n\n"
        f"Сейчас в боте: {count} шт\n\n"
        f"Добавляй по одной строке или сразу несколько (каждая строка = 1 токен).",
        call.message.chat.id, call.message.message_id, reply_markup=markup
    , parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "admin_content_add")
def admin_content_add(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("Назад", callback_data="admin_content"))
    msg = bot.edit_message_text(
        "Введи контент (каждая строка — отдельный токен):\n\nПример:\nlogin1:pass1\nlogin2:pass2\nlogin3:pass3",
        call.message.chat.id, call.message.message_id, reply_markup=markup
    , parse_mode="HTML")
    bot.register_next_step_handler(msg, process_content)

@bot.callback_query_handler(func=lambda call: call.data == "admin_content_clear")
def admin_content_clear(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return
    admin_db = load_admin_db()
    admin_db["content"] = []
    save_admin_db(admin_db)
    bot.answer_callback_query(call.id, "Контент очищен!", show_alert=True)
    admin_content(call)

def process_content(message):
    if not is_admin(message.from_user.id):
        return
    admin_db = load_admin_db()
    content_list = admin_db.get("content", [])
    if isinstance(content_list, str):
        content_list = [content_list] if content_list.strip() else []

    new_lines = [line.strip() for line in message.text.strip().splitlines() if line.strip()]
    content_list.extend(new_lines)
    admin_db["content"] = content_list
    save_admin_db(admin_db)
    bot.send_message(
        message.chat.id,
        f"Добавлено {len(new_lines)} шт.\nВсего в боте: {len(content_list)} шт."
    , parse_mode="HTML")

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    print("Бот запущен!")
    bot.infinity_polling()
