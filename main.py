import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, PreCheckoutQuery
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from config import BOT_TOKEN, FREE_LIMIT
from db import add_user, get_requests, increment_requests, is_paid, set_paid, add_history, get_history
from ai import solve_task
from ocr import extract_text
from payments import get_payment
from utils import simulate_progress, get_repeat_buttons
import tempfile
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

# Хранилища
user_modes = {}
last_task = {}

# Кнопки
mode_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Только ответ", callback_data="mode_answer")],
        [InlineKeyboardButton(text="Пошаговое объяснение", callback_data="mode_full")],
    ]
)

# /start
@dp.message(Command("start"))
async def start(message: Message):
    add_user(message.from_user.id)
    await message.answer(
        f"👋 Привет!\nОтправь задачу (текст или фото), и я решу её 📚\n"
        f"Бесплатно: {FREE_LIMIT} задач\nВыбери режим решения:",
        reply_markup=mode_buttons
    )

# Callback handler
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
            text = "📜 История задач:\n\n"
            for tsk, ans, mode, ts in history:
                text += f"🕒 {ts}\n📝 {tsk[:100]}\n💡 {ans[:150]}\n\n"
            await call.message.answer(text[:4000])
        await call.answer()
    elif call.data == "buy_access":
        prices, description = get_payment()
        try:
            await bot.send_invoice(
                uid,
                title="Доступ к боту",
                description=description,
                provider_token="YOUR_PROVIDER_TOKEN",  # Замените на реальный токен
                currency="USD",
                prices=prices,
                start_parameter="bot_access",
                payload="paid_user"
            )
        except Exception as e:
            logger.error(f"Payment error: {e}")
            await call.message.answer("❌ Ошибка оплаты. Попробуйте позже.")
        await call.answer()
    elif call.data == "repeat_task":
        task = last_task.get(uid)
        if task:
            await process_task(uid, task, call.message)
        await call.answer()
    elif call.data == "new_task":
        await call.message.answer("Отправь новую задачу 📚")
        await call.answer()

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
        await message.answer("❌ Лимит бесплатных задач исчерпан.", reply_markup=markup)
        return
    
    processing_msg = await message.answer("📸 Обрабатываю изображение...")
    
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        downloaded = await bot.download_file(file.file_path)
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(downloaded.read())
            temp_path = tmp.name
        
        await processing_msg.edit_text("🔍 Распознаю текст...")
        extracted_text = extract_text(temp_path, lang='rus+eng')
        os.unlink(temp_path)
        
        if not extracted_text or extracted_text.strip() == "":
            await processing_msg.edit_text("❌ Не удалось распознать текст. Попробуйте более четкое фото.")
            return
        
        await processing_msg.edit_text(f"📝 Распознано: {extracted_text[:100]}...\n\n🤔 Решаю...")
        await process_task(uid, extracted_text, message)
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Photo error: {e}")
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)}")

async def process_task(uid, task, message_obj):
    if not task or task.strip() == "":
        await message_obj.answer("❌ Задача пустая.")
        return
    
    add_user(uid)
    
    if not can_use(uid):
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💰 Купить доступ", callback_data="buy_access")]]
        )
        await message_obj.answer("❌ Лимит исчерпан.", reply_markup=markup)
        return
    
    last_task[uid] = task
    await simulate_progress(message_obj.chat.id, bot)
    mode = user_modes.get(uid, "full")
    
    try:
        answer = solve_task(task, mode)
        increment_requests(uid)
        add_history(uid, task, answer, mode)
        await message_obj.answer(answer, reply_markup=get_repeat_buttons())
    except Exception as e:
        logger.error(f"Task error: {e}")
        await message_obj.answer(f"❌ Ошибка: {str(e)}")

# PreCheckout
@dp.pre_checkout_query()
async def checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

# Успешная оплата
@dp.message(lambda msg: msg.successful_payment)
async def successful_payment(message: Message):
    if message.successful_payment:
        set_paid(message.from_user.id)
        await message.answer("✅ Оплата получена! Безлимитный доступ активирован.")

# Запуск
async def on_startup():
    logger.info("Bot started!")
    webhook_url = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}/webhook"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

async def main():
    # Для Railway используем webhook
    if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        
        # Запускаем сервер
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
        await site.start()
        
        # Устанавливаем webhook
        await bot.set_webhook(f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}/webhook")
        logger.info("Webhook server started")
        
        await asyncio.Event().wait()
    else:
        # Локально используем polling
        logger.info("Starting polling...")
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())