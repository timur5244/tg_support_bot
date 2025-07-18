import logging
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
TOKEN = '7898034491:AAEn4exf46sdViv9VLJQ385lYRQS4p2tXk0'  # замените на ваш токен
SUPPORT_GROUP_ID = -4908403310  # замените на ID вашей группы поддержки

# Глобальные словари для хранения данных заявок и состояний пользователей
applications = {}  # application_id -> {'user_id': ..., 'category': ..., 'text': ..., 'screenshot_file_id': ...}
user_states = {}  # user_id -> {'state': 'choosing_category'/'waiting_text'/'waiting_screenshot', 'category': ..., 'application_id': ...}

# Категории
CATEGORIES = ["1С", "Mpfit", "Битрикс24", "Другое"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Начинаем с приветствия и выбора категории
    keyboard = [
        [InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Здравствуйте! Пожалуйста, выберите категорию обращения:",
        reply_markup=reply_markup
    )
    user_id = update.message.from_user.id
    user_states[user_id] = {'state': 'choosing_category'}

async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data
    user_id = query.from_user.id

    # Запоминаем выбранную категорию и переходим к запросу текста обращения
    user_states[user_id] = {
        'state': 'waiting_text',
        'category': category
    }
    await query.edit_message_text(f"Категория '{category}' выбрана.\nПожалуйста, отправьте текст вашего обращения.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    state_info = user_states.get(user_id)
    if not state_info or state_info.get('state') != 'waiting_text':
        await update.message.reply_text("Пожалуйста, начните с команды /start.")
        return

    category = state_info['category']
    text_message = update.message.text

    # Создаем заявку и сохраняем ее
    application_id = str(uuid.uuid4())
    applications[application_id] = {
        'user_id': user_id,
        'username': update.message.from_user.username,
        'category': category,
        'text': text_message,
        'screenshot_file_id': None
    }

    # Обновляем состояние для ожидания скриншота или пропуска
    user_states[user_id] = {
        'state': 'waiting_screenshot',
        'application_id': application_id
    }

    await update.message.reply_text(
        "Текст обращения сохранен.\nТеперь отправьте скриншот (или напишите /skip для пропуска)."
    )

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    state_info = user_states.get(user_id)
    if not state_info or state_info.get('state') != 'waiting_screenshot':
        await update.message.reply_text("Пожалуйста, сначала отправьте текст обращения или используйте /start.")
        return

    application_id = state_info['application_id']
    
    if not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте фотографию или используйте /skip.")
        return
    
    photo_file_id = update.message.photo[-1].file_id  # самое большое изображение
    
    # Обновляем заявку с фото
    applications[application_id]['screenshot_file_id'] = photo_file_id

    # Формируем сообщение для техподдержки и отправляем его в группу поддержки с ID заявки
    app_data = applications[application_id]
    
    caption_lines = [
        f"🆕 Новое обращение",
        f"🆔 Заявка ID: {application_id}",
        f"👤 Пользователь: @{update.message.from_user.username or update.message.from_user.first_name} (ID: {app_data['user_id']})",
        f"📂 Категория: {app_data['category']}",
        f"💬 Проблема:\n{app_data['text']}",
        f"🖼️ Скриншот: предоставлен"
    ]
    
    caption_text = "\n".join(caption_lines)

    try:
        await context.bot.send_photo(
            chat_id=SUPPORT_GROUP_ID,
            photo=photo_file_id,
            caption=caption_text,
            parse_mode='HTML'
        )
        await update.message.reply_text(f"Ваше обращение получено! Номер заявки:[{application_id}] \nВремя работы  технической поддержки пн-пт 09:00 до 18:00 Специалист свяжется с вами в ближайшее время!")
        
        # Очистка состояния пользователя после завершения заявки
        del user_states[user_id]
        
        # Можно оставить заявку в словаре или удалить ее (по необходимости)
        
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отправке фото: {e}")

async def handle_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /skip — пользователь пропускает добавление скриншота."""
    
    user_id = update.message.from_user.id
    
    state_info = user_states.get(user_id)
    if not state_info or state_info.get('state') != 'waiting_screenshot':
       await update.message.reply_text("Нет активной заявки для пропуска. Начните с /start.")
       return
    
    application_id = state_info['application_id']
    app_data = applications[application_id]
   
    caption_lines = [
       f"🆕 Новое обращение",
       f"🆔 Заявка ID: {application_id}",
       f"👤 Пользователь: @{update.message.from_user.username or update.message.from_user.first_name} (ID: {app_data['user_id']})",
       f"📂 Категория: {app_data['category']}",
       f"💬 Проблема:\n{app_data['text']}",
       f"🖼️ Скриншот не предоставлен"
   ]
   
    caption_text = "\n".join(caption_lines)
   
    try:
       await context.bot.send_message(
           chat_id=SUPPORT_GROUP_ID,
           text=caption_text,
           parse_mode='HTML'
       )
       await update.message.reply_text(f"Ваше обращение получено! Номер заявки: [{application_id}] \nВремя работы  технической поддержки пн-пт 12:00 до 16:00 Специалист свяжется с вами в ближайшее время!")
       
       del user_states[user_id]
       
    except Exception as e:
       await update.message.reply_text(f"Ошибка при отправке сообщения: {e}")

async def support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
     Команда для техподдержки:
      /reply ID_заявки ТЕКСТ_ответа
      Например:
      /reply 123e4567-e89b-12d3-a456-426614174000 Ваше решение проблемы...
      
      Отправляет ответ пользователю по ID заявки.
      
      Предполагается, что команда начинается с "/reply".
      
      Внимание! В реальной реализации стоит добавить проверки безопасности.
      
      Для простоты здесь предполагается правильный ввод.
      
      Можно реализовать так:
      
      """
    
    if len(update.message.text.split(' ', 2)) < 3:
       await update.message.reply_text("Используйте формат:\n/reply ID_заявки ваш_ответ")
       return
    
    parts = update.message.text.split(' ', 2)
    reply_to_application_id = parts[1]
    reply_text = parts[2]
   
    application_data = applications.get(reply_to_application_id)
   
    if not application_data:
       await update.message.reply_text("Заявка не найдена.")
       return
   
    user_chat_id = application_data['user_id']
   
    try:
       await context.bot.send_message(
           chat_id=user_chat_id,
           text=f"Ответ от техподдержки:\n{reply_text}"
       )
       await update.message.reply_text("Ответ успешно отправлен пользователю.")
    except Exception as e:
       await update.message.reply_text(f"Ошибка при отправке ответа пользователю: {e}")

def main():
   app = ApplicationBuilder().token(TOKEN).build()

   app.add_handler(CommandHandler('start', start))
   
   app.add_handler(CallbackQueryHandler(handle_category_selection))
   
   app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
   
   app.add_handler(MessageHandler(filters.PHOTO & (~filters.COMMAND), handle_screenshot))
   
   app.add_handler(CommandHandler('skip', handle_skip))
   
   app.add_handler(CommandHandler('reply', support_reply))
   
   # Запуск бота
   app.run_polling()

if __name__ == '__main__':
   main()