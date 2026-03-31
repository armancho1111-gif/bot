import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, PreCheckoutQuery
from config import BOT_TOKEN, FREE_LIMIT
from db import add_user, get_requests, increment_requests, is_paid, set_paid, add_history, get_history
from ai import solve_task
from ocr import extract_text
from payments import get_payment
from utils import simulate_progress, get_repeat_buttons

# Удаляем временные файлы после использования
import os
import tempfile

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# Режимы
mode_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Только ответ", callback_data="mode_answer")],
        [InlineKeyboardButton(text="Пошаговое объяснение", callback_data="mode_full")],
    ]
)
history_button = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="📜 История задач", callback_data="view_history")]]
)
user_modes = {}
last_task = {}  # для кнопки "Повторить"

# /start
@dp.message(Command("start"))
async def start(message: Message):
    add_user(message.from_user.id)
    await message.answer(
        f"👋 Привет!\nОтправь задачу (текст или фото), и я решу её 📚\n"
        f"Бесплатно: {FREE_LIMIT} задач\nВыбери режим решения:",
        reply_markup=mode_buttons
    )

# Callback
@dp.callback_query()
async def handle_callbacks(call: CallbackQuery):
    uid = call.from_user.id
    if call.data in ["mode_answer", "mode_full"]:
        user_modes[uid] = "answer_only" if call.data=="mode_answer" else "full"
        await call.message.edit_text(f"Выбран режим: {'Только ответ' if call.data=='mode_answer' else 'Пошаговое объяснение'}")
        await call.answer()
    elif call.data == "view_history":
        history = get_history(uid)
        if not history:
            await call.message.answer("📭 История пуста")
        else:
            text = "📜 Ваша история задач:\n\n"
            for tsk, ans, mode, ts in history:
                text += f"🕒 {ts}\n📝 Режим: {'Только ответ' if mode=='answer_only' else 'Пошаговое объяснение'}\n📚 Задача: {tsk[:100]}{'...' if len(tsk)>100 else ''}\n💡 Ответ: {ans[:150]}{'...' if len(ans)>150 else ''}\n\n"
                text += "─" * 30 + "\n\n"
            await call.message.answer(text)
        await call.answer()
    elif call.data == "buy_access":
        prices, description = get_payment()
        await bot.send_invoice(
            uid,
            title="Доступ к боту",
            description=description,
            provider_token="YOUR_PROVIDER_TOKEN",
            currency="USD",
            prices=prices,
            start_parameter="bot_access",
            payload="paid_user"
        )
    elif call.data == "repeat_task":
        task = last_task.get(uid)
        if task:
            await process_task(uid, task, call.message)
        else:
            await call.message.answer("❌ Нет сохраненной задачи для повторения")
        await call.answer()
    elif call.data == "new_task":
        await call.message.answer("📚 Отправьте новую задачу (текстом или фото)")
        await call.answer()

# Проверка лимита
def can_use(uid):
    return is_paid(uid) or get_requests(uid) < FREE_LIMIT

# Обработка текста
@dp.message(lambda msg: msg.text and not msg.text.startswith('/'))
async def handle_text(message: Message):
    await process_task(message.from_user.id, message.text, message)

# Обработка фото
@dp.message(lambda msg: msg.photo)
async def handle_photo(message: Message):
    uid = message.from_user.id
    add_user(uid)
    
    if not can_use(uid):
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💰 Купить доступ", callback_data="buy_access")]]
        )
        await message.answer("❌ Лимит бесплатных задач исчерпан. Приобретите доступ для продолжения!", reply_markup=markup)
        return
    
    # Отправляем сообщение о начале обработки
    processing_msg = await message.answer("📸 Обрабатываю изображение...")
    
    try:
        # Скачиваем фото
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        downloaded = await bot.download_file(file.file_path)
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            tmp_file.write(downloaded.read())
            temp_path = tmp_file.name
        
        # Извлекаем текст через OCR
        await processing_msg.edit_text("🔍 Распознаю текст...")
        extracted_text = extract_text(temp_path, lang='rus+eng')
        
        # Удаляем временный файл
        os.unlink(temp_path)
        
        # Проверяем, удалось ли извлечь текст
        if not extracted_text or extracted_text.strip() == "":
            await processing_msg.edit_text(
                "❌ Не удалось распознать текст на изображении.\n\n"
                "💡 Попробуйте:\n"
                "• Отправить более четкое фото\n"
                "• Убедиться, что текст хорошо виден\n"
                "• Ввести текст вручную"
            )
            return
        
        # Обновляем сообщение
        preview = extracted_text[:200] + '...' if len(extracted_text) > 200 else extracted_text
        await processing_msg.edit_text(
            f"📝 Распознанный текст:\n{preview}\n\n"
            f"🤔 Решаю задачу..."
        )
        
        # Вызываем обработку с извлеченным текстом
        await process_task(uid, extracted_text, message)
        
        # Удаляем временное сообщение
        await processing_msg.delete()
        
    except Exception as e:
        logging.error(f"Error processing photo: {e}")
        await processing_msg.edit_text(
            f"❌ Ошибка при обработке изображения: {str(e)}\n"
            f"Попробуйте отправить текст вручную."
        )

# Основная функция обработки
async def process_task(uid, task, message_obj):
    # Проверяем, что задача не пустая
    if not task or task.strip() == "":
        await message_obj.answer(
            "❌ Задача не распознана или пустая.\n"
            "Пожалуйста, отправьте текст или более четкое фото."
        )
        return
    
    add_user(uid)
    
    if not can_use(uid):
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💰 Купить доступ", callback_data="buy_access")]]
        )
        await message_obj.answer(
            "❌ Лимит бесплатных задач исчерпан. Приобретите доступ для продолжения!",
            reply_markup=markup
        )
        return

    # Сохраняем задачу для возможности повтора
    last_task[uid] = task
    
    # Показываем прогресс
    progress_msg = await simulate_progress(message_obj.chat.id, bot)
    
    # Получаем режим
    mode = user_modes.get(uid, "full")
    
    try:
        # Решаем задачу
        answer = solve_task(task, mode)
        
        # Обновляем статистику
        increment_requests(uid)
        add_history(uid, task, answer, mode)
        
        # Удаляем сообщение с прогрессом
        await progress_msg.delete()
        
        # Отправляем ответ
        await message_obj.answer(
            f"✅ **Решение:**\n\n{answer}",
            reply_markup=get_repeat_buttons(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logging.error(f"Error solving task: {e}")
        await progress_msg.delete()
        await message_obj.answer(
            f"❌ Произошла ошибка при решении задачи: {str(e)}\n"
            f"Попробуйте позже или отправьте задачу иначе."
        )

# PreCheckout
@dp.pre_checkout_query()
async def checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

# Успешная оплата
@dp.message(lambda msg: msg.successful_payment)
async def successful_payment(message: Message):
    if message.successful_payment:
        set_paid(message.from_user.id)
        await message.answer(
            "✅ **Оплата успешно получена!**\n\n"
            "🎉 Безлимитный доступ активирован!\n"
            "Теперь вы можете решать сколько угодно задач.\n\n"
            "Отправляйте новые задачи и я помогу их решить! 📚",
            reply_markup=get_repeat_buttons(),
            parse_mode="HTML"
        )

# Обработка ошибок
@dp.errors()
async def error_handler(update, exception):
    logging.error(f"Update: {update}, Exception: {exception}")
    return True

async def main():
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())