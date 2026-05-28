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
SUPPORT_LINK = "https://t.me/your_admin_username"  # <-- замени на свой юз поддержки
DB_FILE = "users_db.json"
ADMIN_DB = "admin_db.json"
INVOICE_DB = "invoices_db.json"

bot = telebot.TeleBot(BOT_TOKEN)

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
        "content": "login:password",
        "channels": []
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
                invoice = invoices[0]
                return {
                    "status": invoice.get("status"),
                    "amount": invoice.get("amount"),
                    "paid_amount": invoice.get("paid_amount")
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
                users[str(user_id)]["balance"] += amount_usd
                save_users(users)
            invoices = load_invoices()
            if invoice_id in invoices:
                invoices[invoice_id]["paid"] = True
                save_invoices(invoices)
            try:
                bot.edit_message_text(
                    f"Платеж успешно получен!\n\nВыплачено: {amount_usd}$\nБаланс пополнен на {amount_usd}$",
                    chat_id,
                    message_id
                )
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
                bot.edit_message_text(
                    "Инвойс истек! Время для оплаты истекло.",
                    chat_id,
                    message_id
                )
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
    """Принимает @username, https://t.me/username, ID — возвращает нужный формат"""
    channel_input = channel_input.strip()
    # Ссылка типа https://t.me/username или t.me/username
    if "t.me/" in channel_input:
        username = channel_input.split("t.me/")[-1].strip("/").strip()
        # Убираем возможные параметры
        username = username.split("?")[0].split("/")[0]
        return f"@{username}"
    # Уже @username
    if channel_input.startswith("@"):
        return channel_input
    # Числовой ID
    try:
        return int(channel_input)
    except ValueError:
        return None

def get_channel_invite_url(channel_id):
    """Формирует ссылку на канал для кнопки"""
    if isinstance(channel_id, str) and channel_id.startswith("@"):
        return f"https://t.me/{channel_id[1:]}"
    elif isinstance(channel_id, int):
        return f"https://t.me/c/{str(channel_id).replace('-100', '')}"
    return None

def is_subscribed_to_all(user_id):
    admin_db = load_admin_db()
    channels = admin_db.get("channels", [])
    if not channels:
        return True  # Нет каналов — даём доступ сразу
    for channel_id in channels:
        try:
            chat_member = bot.get_chat_member(channel_id, user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def register_user(user):
    """Регистрирует нового юзера если нет в БД"""
    users = load_users()
    user_id = user.id
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": user.username or "Unknown",
            "id": user_id,
            "balance": 0.05,
            "joined": datetime.now().isoformat()
        }
        save_users(users)

# ==================== ГЛАВНОЕ МЕНЮ ====================
def show_main_menu(chat_id, user_id):
    users = load_users()
    user = users.get(str(user_id), {})
    balance = user.get("balance", 0)
    username = user.get("username", "Unknown")

    # Профиль с рамкой как на скрине
    message = (
        "Kretros Shop\n"
        "\n"
        "——————————————\n"
        f"|User: @{username}!\n"
        f"|ID: {user_id}\n"
        f"|Баланс: {balance}$\n"
        "——————————————"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔑 Купить Token", callback_data="buy_token"),
        types.InlineKeyboardButton("🔵 Баланс", callback_data="check_balance"),
        types.InlineKeyboardButton("⚙️ Правила", callback_data="rules"),
        types.InlineKeyboardButton("🧡 Поддержка", url=SUPPORT_LINK)
    )

    bot.send_message(chat_id, message, reply_markup=markup)

# ==================== /start ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    if is_user_banned(user_id):
        return

    users = load_users()

    # Уже зарегистрирован — сразу меню
    if str(user_id) in users:
        show_main_menu(message.chat.id, user_id)
        return

    admin_db = load_admin_db()
    channels = admin_db.get("channels", [])

    # Каналов нет — даём доступ сразу
    if not channels:
        register_user(message.from_user)
        show_main_menu(message.chat.id, user_id)
        return

    # Уже подписан на все каналы — даём доступ
    if is_subscribed_to_all(user_id):
        register_user(message.from_user)
        show_main_menu(message.chat.id, user_id)
        return

    # Просим подписаться
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, channel in enumerate(channels, 1):
        url = get_channel_invite_url(channel)
        if url:
            markup.add(types.InlineKeyboardButton(f"{i} 🔗 Канал", url=url))
    markup.add(types.InlineKeyboardButton("2 ✅ Подписался", callback_data="check_subscription"))

    bot.send_message(
        message.chat.id,
        "🔔 Для доступа в бот нужно подписаться на канал ⚠️\n\n"
        "✅ После подписки нажмите /start",
        reply_markup=markup
    )

# ==================== ПРОВЕРКА ПОДПИСКИ ====================
@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription(call):
    user_id = call.from_user.id

    if is_user_banned(user_id):
        return

    if is_subscribed_to_all(user_id):
        register_user(call.from_user)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message.chat.id, user_id)
    else:
        bot.answer_callback_query(call.id, "Подпишись на ВСЕ каналы!", show_alert=True)

# ==================== КУПИТЬ ТОКЕН ====================
@bot.callback_query_handler(func=lambda call: call.data == "buy_token")
def buy_token(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    admin_db = load_admin_db()
    price = admin_db["product_price"]
    min_purchase = admin_db["min_purchase"]
    tokens_left = admin_db["tokens_in_bot"]

    message = (
        "Кнопка купить токен :\n"
        "\n"
        "🔵 TOKEN\n"
        "——————————————\n"
        f"Ценник: {price} 💎\n"
        f"Мин покупка: {min_purchase} шт 💚\n"
        f"Кол-во в боте: {tokens_left} шт 🔄"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💳 Оплатить", callback_data="payment"))

    bot.edit_message_text(
        message,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ==================== ОПЛАТА ====================
@bot.callback_query_handler(func=lambda call: call.data == "payment")
def payment(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    admin_db = load_admin_db()
    min_purchase = admin_db["min_purchase"]

    msg = bot.send_message(
        call.message.chat.id,
        f"Введите количество токенов (мин: {min_purchase}):"
    )
    bot.register_next_step_handler(msg, process_quantity, call.message.message_id)

def process_quantity(message, old_msg_id):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if is_user_banned(user_id):
        return

    try:
        admin_db = load_admin_db()
        quantity = int(message.text)
        min_purchase = admin_db["min_purchase"]
        price = admin_db["product_price"]
        tokens_left = admin_db["tokens_in_bot"]

        if quantity < min_purchase:
            bot.send_message(chat_id, f"Минимум {min_purchase} токенов!")
            return

        if quantity > tokens_left:
            bot.send_message(chat_id, "Недостаточно токенов в боте!")
            return

        total_price = quantity * price
        users = load_users()
        user_balance = users[str(user_id)]["balance"]

        if user_balance < total_price:
            bot.send_message(chat_id, f"Недостаточно средств!\nНужно: {total_price}$\nУ вас: {user_balance}$")
            return

        users[str(user_id)]["balance"] -= total_price
        save_users(users)

        admin_db["tokens_in_bot"] -= quantity
        save_admin_db(admin_db)

        content = admin_db["content"]
        bot.send_message(
            chat_id,
            f"Покупка успешна!\n\nВаш контент:\n{content}\n\nСпасибо за покупку!"
        )

        show_main_menu(chat_id, user_id)

    except ValueError:
        bot.send_message(chat_id, "Введи число!")

# ==================== БАЛАНС ====================
@bot.callback_query_handler(func=lambda call: call.data == "check_balance")
def check_balance(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    users = load_users()
    user = users.get(str(user_id), {})
    balance = user.get("balance", 0)

    message = (
        "Кнопка баланс :\n"
        "\n"
        f"Ваш баланс : {balance} 🟡"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="refill_balance"))

    bot.edit_message_text(
        message,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ==================== ПОПОЛНИТЬ БАЛАНС ====================
@bot.callback_query_handler(func=lambda call: call.data == "refill_balance")
def refill_balance(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    admin_db = load_admin_db()
    min_amount = admin_db.get("product_price", 5)

    # Редактируем сообщение — один текст, без второго send_message
    bot.edit_message_text(
        f"🔵 Пополнение баланса\n\nВведите сумму от {min_amount} 🟡",
        call.message.chat.id,
        call.message.message_id
    )

    # Ждем ввод суммы
    bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_refill)

def process_refill(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if is_user_banned(user_id):
        return

    try:
        amount = float(message.text)
        admin_db = load_admin_db()
        min_amount = admin_db.get("product_price", 5)

        if amount < min_amount:
            bot.send_message(chat_id, f"Минимум {min_amount}$!")
            return

        invoice = create_invoice(amount, user_id)

        if not invoice:
            bot.send_message(chat_id, "Ошибка создания инвойса. Попробуй позже.")
            return

        invoices = load_invoices()
        invoices[invoice["invoice_id"]] = invoice
        save_invoices(invoices)

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Оплатить", url=invoice['pay_url']))

        msg = bot.send_message(
            chat_id,
            f"Счет на оплату\n\nСумма: {amount}$\nМетод: CryptoBot (USDT)\n\nПроверяю статус платежа...",
            reply_markup=markup
        )

        thread = threading.Thread(
            target=monitor_invoice,
            args=(invoice["invoice_id"], user_id, chat_id, msg.message_id, amount)
        )
        thread.daemon = True
        thread.start()

    except ValueError:
        bot.send_message(chat_id, "Введи число!")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {str(e)}")

# ==================== ПРАВИЛА ====================
@bot.callback_query_handler(func=lambda call: call.data == "rules")
def rules(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        return

    message = (
        "правила:\n"
        "\n"
        "1 Баланс с бота не выводится.\n"
        "\n"
        "2 Гарантия на токены составляет 30 минут после покупки.\n"
        "\n"
        "3 Любая попытка обмануть сервис равносильна блокировке."
    )

    bot.edit_message_text(
        message,
        call.message.chat.id,
        call.message.message_id
    )

# ==================== АДМИНКА ====================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "Нет доступа!")
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

    bot.send_message(message.chat.id, "Админ Панель", reply_markup=markup)

# ==================== АДМИН: КАНАЛЫ ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_channels")
def admin_channels(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    admin_db = load_admin_db()
    channels = admin_db.get("channels", [])

    message = "Управление Каналами\n\n"
    if channels:
        message += "Активные каналы:\n"
        for idx, ch_id in enumerate(channels, 1):
            message += f"{idx}. {ch_id}\n"
    else:
        message += "Каналы не добавлены\n"

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("Добавить канал", callback_data="admin_add_channel"))
    if channels:
        markup.add(types.InlineKeyboardButton("Удалить канал", callback_data="admin_remove_channel"))

    bot.edit_message_text(
        message,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_channel")
def admin_add_channel(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    msg = bot.send_message(
        call.message.chat.id,
        "Введи ID канала, @username или ссылку t.me/...\nПример: @my_channel или https://t.me/my_channel"
    )
    bot.register_next_step_handler(msg, process_add_channel)

def process_add_channel(message):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        return

    channel_input = message.text.strip()
    channel_id = resolve_channel_id(channel_input)

    if channel_id is None:
        bot.send_message(message.chat.id, "Неверный формат! Введи @username, ссылку t.me/... или числовой ID.")
        return

    if not check_bot_admin_in_channel(channel_id):
        bot.send_message(
            message.chat.id,
            f"Ошибка!\n\nБот должен быть администратором в канале {channel_input}\n\nДобавь бота админом в канал и попробуй снова!"
        )
        return

    admin_db = load_admin_db()
    channels = admin_db.get("channels", [])

    if channel_id not in channels:
        channels.append(channel_id)
        admin_db["channels"] = channels
        save_admin_db(admin_db)
        bot.send_message(message.chat.id, f"Канал {channel_input} добавлен!")
    else:
        bot.send_message(message.chat.id, "Канал уже в списке")

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

    message = "Выбери канал для удаления:\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    for idx, ch_id in enumerate(channels, 1):
        message += f"{idx}. {ch_id}\n"
        markup.add(
            types.InlineKeyboardButton(
                f"Удалить {ch_id}",
                callback_data=f"remove_ch_{idx-1}"
            )
        )

    bot.edit_message_text(
        message,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

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
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}", show_alert=True)

# ==================== АДМИН: БАЛАНС ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_give_balance")
def admin_give_balance(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    msg = bot.send_message(call.message.chat.id, "Введи ID пользователя:")
    bot.register_next_step_handler(msg, admin_get_user_id_for_balance)

def admin_get_user_id_for_balance(message):
    try:
        target_user_id = int(message.text)
        msg = bot.send_message(message.chat.id, "Введи сумму для выдачи:")
        bot.register_next_step_handler(msg, admin_process_balance, target_user_id)
    except ValueError:
        bot.send_message(message.chat.id, "ID должно быть числом!")

def admin_process_balance(message, target_user_id):
    try:
        amount = float(message.text)
        users = load_users()

        if str(target_user_id) not in users:
            users[str(target_user_id)] = {
                "username": "Unknown",
                "id": target_user_id,
                "balance": 0,
                "joined": datetime.now().isoformat()
            }

        users[str(target_user_id)]["balance"] += amount
        save_users(users)
        bot.send_message(message.chat.id, f"Выдано {amount}$ пользователю {target_user_id}")
    except ValueError:
        bot.send_message(message.chat.id, "Введи число!")

# ==================== АДМИН: БАН ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_ban")
def admin_ban(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    msg = bot.send_message(call.message.chat.id, "Введи ID пользователя для бана/анбана:")
    bot.register_next_step_handler(msg, process_ban)

def process_ban(message):
    try:
        target_user_id = str(int(message.text))
        admin_db = load_admin_db()

        if target_user_id in admin_db["banned_users"]:
            admin_db["banned_users"].remove(target_user_id)
            bot.send_message(message.chat.id, f"Пользователь {target_user_id} разбанен")
        else:
            admin_db["banned_users"].append(target_user_id)
            bot.send_message(message.chat.id, f"Пользователь {target_user_id} забанен")

        save_admin_db(admin_db)
    except ValueError:
        bot.send_message(message.chat.id, "ID должно быть числом!")

# ==================== АДМИН: ОСТАТОК ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_stock")
def admin_stock(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    msg = bot.send_message(call.message.chat.id, "Введи новое количество токенов:")
    bot.register_next_step_handler(msg, process_stock)

def process_stock(message):
    try:
        quantity = int(message.text)
        admin_db = load_admin_db()
        admin_db["tokens_in_bot"] = quantity
        save_admin_db(admin_db)
        bot.send_message(message.chat.id, f"Остаток изменен на {quantity}")
    except ValueError:
        bot.send_message(message.chat.id, "Введи число!")

# ==================== АДМИН: ЦЕНА ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_price")
def admin_price(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    msg = bot.send_message(call.message.chat.id, "Введи новую цену токена:")
    bot.register_next_step_handler(msg, process_price)

def process_price(message):
    try:
        price = float(message.text)
        admin_db = load_admin_db()
        admin_db["product_price"] = price
        save_admin_db(admin_db)
        bot.send_message(message.chat.id, f"Цена изменена на {price}$")
    except ValueError:
        bot.send_message(message.chat.id, "Введи число!")

# ==================== АДМИН: МИН КОЛ-ВО ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_min_qty")
def admin_min_qty(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    msg = bot.send_message(call.message.chat.id, "Введи минимальное количество покупки:")
    bot.register_next_step_handler(msg, process_min_qty)

def process_min_qty(message):
    try:
        min_qty = int(message.text)
        admin_db = load_admin_db()
        admin_db["min_purchase"] = min_qty
        save_admin_db(admin_db)
        bot.send_message(message.chat.id, f"Минимум количество изменено на {min_qty}")
    except ValueError:
        bot.send_message(message.chat.id, "Введи число!")

# ==================== АДМИН: КОНТЕНТ ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_content")
def admin_content(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    msg = bot.send_message(call.message.chat.id, "Введи новый контент (например: login:password):")
    bot.register_next_step_handler(msg, process_content)

def process_content(message):
    admin_db = load_admin_db()
    admin_db["content"] = message.text
    save_admin_db(admin_db)
    bot.send_message(message.chat.id, "Контент изменен")

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    print("Бот запущен!")
    bot.infinity_polling()
