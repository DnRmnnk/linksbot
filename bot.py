import os
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Вставь свой токен
TOKEN = '7904381577:AAFmEVH_-Ge9BhG1v9cL_QEf_ORvegq1PS4'

# Путь к файлу для хранения каналов
CHANNELS_FILE = "channels.txt"

# Список ID пользователей, которым разрешено пользоваться ботом
ALLOWED_USERS = [353688342]  # Замените на реальные ID пользователей

# Список ID администраторов, которые могут добавлять каналы
ADMINS = [353688342]  # Замените на реальные ID администраторов

# Функция для проверки, есть ли доступ у пользователя
def is_allowed(user_id):
    return user_id in ALLOWED_USERS

# Функция для проверки, является ли пользователь администратором
def is_admin(user_id):
    return user_id in ADMINS

# Функция для отображения клавиатуры в зависимости от прав доступа
def get_main_keyboard(user_id):
    if is_admin(user_id):
        # Клавиатура для администратора
        keyboard = [
            [KeyboardButton("Добавить канал"), KeyboardButton("Создать ссылку")],
            [KeyboardButton("Доступные каналы")]
        ]
    else:
        # Клавиатура для обычного пользователя
        keyboard = [
            [KeyboardButton("Создать ссылку"), KeyboardButton("Доступные каналы")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Команда для начала работы
async def start(update: Update, context):
    user_id = update.message.from_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return

    await update.message.reply_text(
        "Добро пожаловать! Выберите действие:",
        reply_markup=get_main_keyboard(user_id)
    )

# Обработчик текстовых сообщений
async def handle_message(update: Update, context):
    user_id = update.message.from_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return

    text = update.message.text

    if text == "Добавить канал" and is_admin(user_id):
        await update.message.reply_text("Введите ID канала в формате -123456789.")
        context.user_data['state'] = 'waiting_for_channel_id'
    elif text == "Создать ссылку":
        channels = load_channels()
        if channels:
            channel_buttons = [KeyboardButton(channel['name']) for channel in channels]
            reply_markup = ReplyKeyboardMarkup.from_column(channel_buttons, resize_keyboard=True)
            await update.message.reply_text("Выберите канал для создания ссылки:", reply_markup=reply_markup)
            context.user_data['state'] = 'selecting_channel'
        else:
            await update.message.reply_text("Нет доступных каналов. Сначала добавьте канал.", reply_markup=get_main_keyboard(user_id))
    elif text == "Доступные каналы":
        channels = load_channels()
        if channels:
            await update.message.reply_text(
                "Текущие каналы:\n" + "\n".join([f"{channel['id']} - {channel['name']}" for channel in channels]),
                reply_markup=get_main_keyboard(user_id)
            )
        else:
            await update.message.reply_text("Нет доступных каналов.", reply_markup=get_main_keyboard(user_id))
    elif context.user_data.get('state') == 'waiting_for_channel_id' and is_admin(user_id):
        await handle_channel_id_input(update, context)
    elif context.user_data.get('state') == 'selecting_channel':
        await handle_channel_selection(update, context)
    elif context.user_data.get('state') == 'waiting_for_link_name':
        await handle_link_name_input(update, context)
    elif context.user_data.get('state') == 'waiting_for_link_quantity':
        await handle_link_quantity_input(update, context)
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки на клавиатуре.", reply_markup=get_main_keyboard(user_id))

# Обработчик ввода ID канала
async def handle_channel_id_input(update: Update, context):
    channel_id = update.message.text.strip()
    if not channel_id.startswith('-') or not channel_id[1:].isdigit():
        await update.message.reply_text("ID канала должен быть числом с отрицательным знаком. Попробуйте еще раз.")
        return
    try:
        channel = await context.bot.get_chat(channel_id)
        channel_name = channel.title or f"Канал {channel_id}"
        save_channel(channel_id, channel_name)
        await update.message.reply_text(f"Канал '{channel_name}' добавлен!", reply_markup=get_main_keyboard(update.message.from_user.id))
        context.user_data['state'] = ''
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}. Попробуйте снова.", reply_markup=get_main_keyboard(update.message.from_user.id))

# Обработчик выбора канала
async def handle_channel_selection(update: Update, context):
    channel_name = update.message.text
    channels = load_channels()
    selected_channel = next((ch for ch in channels if ch["name"] == channel_name), None)
    if selected_channel:
        context.user_data['selected_channel_id'] = selected_channel['id']
        await update.message.reply_text("Введите название для создаваемых ссылок.", reply_markup=get_main_keyboard(update.message.from_user.id))
        context.user_data['state'] = 'waiting_for_link_name'
    else:
        await update.message.reply_text("Выберите корректный канал.", reply_markup=get_main_keyboard(update.message.from_user.id))

# Обработчик ввода названия ссылки
async def handle_link_name_input(update: Update, context):
    link_name = update.message.text.strip()
    context.user_data['link_name'] = link_name
    await update.message.reply_text("Введите количество ссылок, которые хотите создать.")
    context.user_data['state'] = 'waiting_for_link_quantity'

# Обработчик ввода количества ссылок
async def handle_link_quantity_input(update: Update, context):
    try:
        quantity = int(update.message.text.strip())
        if quantity <= 0:
            await update.message.reply_text("Количество ссылок должно быть больше 0.")
            return
        link_name = context.user_data.get('link_name')
        channel_id = context.user_data.get('selected_channel_id')

        # Создание и отправка ссылок
        links = []
        for i in range(quantity):
            invite_link = await context.bot.create_chat_invite_link(
                chat_id=channel_id,
                name=f"{link_name}{i + 1}",
                creates_join_request=True
            )
            links.append(f"{invite_link.invite_link} | {link_name}{i + 1}")

        await update.message.reply_text(
            "Созданные ссылки:\n" + "\n".join(links),
            reply_markup=get_main_keyboard(update.message.from_user.id)
        )
        context.user_data['state'] = ''
    except ValueError:
        await update.message.reply_text("Введите корректное количество.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при создании ссылок: {e}.")

# Загрузка каналов из файла
def load_channels():
    channels = []
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r") as file:
            for line in file:
                channel_id, channel_name = line.strip().split(',')
                channels.append({"id": channel_id, "name": channel_name})
    return channels

# Функция сохранения канала
def save_channel(channel_id, channel_name):
    with open(CHANNELS_FILE, "a") as file:
        file.write(f"{channel_id},{channel_name}\n")

# Основная функция для запуска бота
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
