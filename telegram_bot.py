import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Подключение к Google Sheets
def connect_to_sheet():
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    
    # Открываем Google таблицу по ссылке
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/19WXJURsTNR4-ATY-QJje9GohhZDZPNOFx8l7nWrZJ6g/edit?usp=sharing")
    worksheet = sheet.get_worksheet(0)  # Работаем с первой вкладкой таблицы
    return worksheet

# Команда /start - предоставляет выбор предметов
async def start(update: Update, context):
    worksheet = connect_to_sheet()
    
    # Получаем список предметов (A9:A32)
    items = worksheet.col_values(1)[8:32]  # Строки с 9 по 32
    
    # Фильтруем пустые строки
    items = [item for item in items if item]

    # Ограничиваем callback_data до индексов предметов
    keyboard = [[InlineKeyboardButton(item, callback_data=f"item_{i}")] for i, item in enumerate(items)]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Выберите предмет:", reply_markup=reply_markup)

# Обработка выбора предмета
async def handle_item_choice(update: Update, context):
    query = update.callback_query
    callback_data = query.data

    if callback_data.startswith("item_"):
        item_index = int(callback_data.split("_")[1])  # Получаем индекс выбранного предмета
        
        worksheet = connect_to_sheet()
        items = worksheet.col_values(1)[8:32]  # Получаем список предметов снова
        item = items[item_index]  # Получаем название предмета
        context.user_data['item'] = item  # Сохраняем выбранный предмет

        item_row = worksheet.find(item).row  # Ищем строку предмета

        # Получаем список дат (C8:I8)
        dates = worksheet.row_values(8)[2:9]  # Даты в строке 8, с колонок C по I
        available_dates = []

        # Проверяем, какие даты еще не забронированы (например, C9 для предмета в A9)
        for i, date in enumerate(dates):
            reservation_status = worksheet.cell(item_row, i + 3).value  # Проверяем ячейку по строке предмета
            if not reservation_status:  # Если ячейка пуста, добавляем дату в доступные
                available_dates.append((date, i))  # Добавляем дату и её индекс

        # Если нет доступных дат
        if not available_dates:
            await query.message.reply_text(f"Для предмета '{item}' нет доступных дат.")
            return

        # Формируем кнопки с доступными датами, передаем индекс даты в callback_data
        keyboard = [[InlineKeyboardButton(date, callback_data=f"date_{index}")] for date, index in available_dates]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отображаем сами даты в кнопках
        await query.message.reply_text(f"Выберите дату для предмета '{item}':", reply_markup=reply_markup)

# Обработка выбора даты
async def handle_date_choice(update: Update, context):
    query = update.callback_query
    callback_data = query.data

    if callback_data.startswith("date_"):
        date_index = int(callback_data.split("_")[1])  # Получаем индекс выбранной даты
        item = context.user_data['item']  # Получаем сохраненный предмет

        worksheet = connect_to_sheet()

        # Ищем строку, соответствующую выбранному предмету
        item_row = worksheet.find(item).row

        # Получаем список дат (C8:I8) снова
        dates = worksheet.row_values(8)[2:9]  # Даты в строке 8, с колонок C по I
        selected_date = dates[date_index]  # Получаем выбранную дату по индексу

        context.user_data['date'] = selected_date  # Сохраняем выбранную дату

        await query.message.reply_text(f"Вы выбрали дату: {selected_date}. Пожалуйста, введите свой никнейм:")

# Обработка никнейма и бронирования
async def handle_nickname(update: Update, context):
    nickname = update.message.text
    context.user_data['nickname'] = nickname

    item = context.user_data['item']
    date = context.user_data['date']

    worksheet = connect_to_sheet()

    # Находим строку с предметом и колонку с датой
    item_row = worksheet.find(item).row
    dates = worksheet.row_values(8)[2:9]  # Даты в строке 8, колонки C:I
    date_col = dates.index(date) + 3  # Колонка с нужной датой

    # Проверяем, не забронирован ли предмет на выбранную дату
    reservation_status = worksheet.cell(item_row, date_col).value
    if reservation_status:
        await update.message.reply_text(f"Извините, предмет '{item}' уже забронирован на дату {date}.")
    else:
        # Записываем никнейм в таблицу
        worksheet.update_cell(item_row, date_col, nickname)
        await update.message.reply_text(f"Предмет '{item}' успешно забронирован на {date} под ником {nickname}.")

if __name__ == '__main__':
    app = ApplicationBuilder().token('7474312977:AAHpnZpfWG9evMgn3Bbh41Do1b6Ln41_7Kk').build()

    # Обработчики команд и сообщений
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_item_choice, pattern="item_"))  # Обработка выбора предмета
    app.add_handler(CallbackQueryHandler(handle_date_choice, pattern="date_"))  # Обработка выбора даты
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_nickname))  # Никнейм

    # Запуск бота
    app.run_polling()
