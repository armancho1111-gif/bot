import asyncio
import logging
import os
import tempfile

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PreCheckoutQuery,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from ai import extract_task_from_image, normalize_task_text, solve_task
from config import BOT_TOKEN, FREE_LIMIT, OCR_LANGUAGE
from db import (
    add_history,
    add_user,
    get_history,
    get_requests,
    increment_requests,
    is_paid,
    set_paid,
)
from ocr import extract_text
from payments import get_payment
from utils import get_repeat_buttons, simulate_progress

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

user_modes = {}
last_task = {}

mode_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Только ответ", callback_data="mode_answer")],
        [InlineKeyboardButton(text="Пошаговое объяснение", callback_data="mode_full")],
    ]
)


def can_use(uid):
    return is_paid(uid) or get_requests(uid) < FREE_LIMIT


def is_empty_task(task):
    return normalize_task_text(task) == ""


def build_task_from_sources(caption, vision_text, ocr_text):
    caption = normalize_task_text(caption)
    vision_text = normalize_task_text(vision_text)
    ocr_text = normalize_task_text(ocr_text)

    if vision_text and caption:
        if caption.lower() in vision_text.lower():
            return vision_text
        return f"{vision_text}\n\nДополнительный комментарий пользователя:\n{caption}"

    if vision_text:
        return vision_text

    if caption and ocr_text:
        return f"{caption}\n\nТекст, распознанный с изображения:\n{ocr_text}"

    if caption:
        return caption

    return ocr_text


@dp.message(Command("start"))
async def start(message: Message):
    add_user(message.from_user.id)
    await message.answer(
        (
            f"👋 Привет!\n"
            f"Отправь задачу текстом или фотографией, и я помогу ее решить.\n"
            f"Бесплатно доступно: {FREE_LIMIT} задач.\n"
            f"Выбери режим ответа:"
        ),
        reply_markup=mode_buttons,
    )


@dp.callback_query()
async def handle_callbacks(call: CallbackQuery):
    uid = call.from_user.id

    if call.data in ["mode_answer", "mode_full"]:
        user_modes[uid] = "answer_only" if call.data == "mode_answer" else "full"
        mode_text = "Только ответ" if call.data == "mode_answer" else "Пошаговое объяснение"
        await call.message.edit_text(f"Выбран режим: {mode_text}")
        await call.answer()
        return

    if call.data == "view_history":
        history = get_history(uid)
        if not history:
            await call.message.answer("📭 История пока пустая.")
        else:
            text = "📜 История задач:\n\n"
            for task, answer, mode, ts in history:
                text += f"🕒 {ts}\n📝 {task[:100]}\n💡 {answer[:150]}\n\n"
            await call.message.answer(text[:4000])
        await call.answer()
        return

    if call.data == "buy_access":
        prices, description = get_payment()
        try:
            await bot.send_invoice(
                uid,
                title="Доступ к боту",
                description=description,
                provider_token="YOUR_PROVIDER_TOKEN",
                currency="USD",
                prices=prices,
                start_parameter="bot_access",
                payload="paid_user",
            )
        except Exception as e:
            logger.error("Payment error: %s", e)
            await call.message.answer("❌ Ошибка оплаты. Попробуйте позже.")
        await call.answer()
        return

    if call.data == "repeat_task":
        task = last_task.get(uid)
        if task:
            await process_task(uid, task, call.message)
        await call.answer()
        return

    if call.data == "new_task":
        await call.message.answer("Отправь новую задачу 📚")
        await call.answer()


@dp.message(lambda msg: msg.text and not msg.text.startswith("/"))
async def handle_text(message: Message):
    await process_task(message.from_user.id, message.text, message)


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

    processing_msg = await message.answer("📷 Обрабатываю изображение...")
    temp_path = None

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        downloaded = await bot.download_file(file.file_path)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(downloaded.read())
            temp_path = tmp.name

        caption = normalize_task_text(message.caption)

        await processing_msg.edit_text("🧠 Понимаю, что изображено на фото...")
        vision_text = extract_task_from_image(temp_path, caption=caption)

        ocr_text = ""
        if not vision_text:
            await processing_msg.edit_text("🔎 Vision не нашел условие, пробую OCR...")
            ocr_text = extract_text(temp_path, lang=OCR_LANGUAGE)

        extracted_text = build_task_from_sources(caption, vision_text, ocr_text)
        if is_empty_task(extracted_text):
            await processing_msg.edit_text(
                "❌ Не удалось понять условие задачи на фото. "
                "Попробуйте более четкое изображение или добавьте подпись с текстом задачи."
            )
            return

        preview = extracted_text.replace("\n", " ")[:140]
        suffix = "..." if len(extracted_text) > 140 else ""
        await processing_msg.edit_text(f"📝 Нашел задачу: {preview}{suffix}\n\n🤔 Решаю...")

        await process_task(uid, extracted_text, message)
        await processing_msg.delete()

    except Exception as e:
        logger.error("Photo error: %s", e)
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


async def process_task(uid, task, message_obj):
    task = normalize_task_text(task)
    if not task:
        await message_obj.answer("❌ Задача пустая или не распознана.")
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
        logger.error("Task error: %s", e)
        await message_obj.answer(f"❌ Ошибка: {str(e)}")


@dp.pre_checkout_query()
async def checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(lambda msg: msg.successful_payment)
async def successful_payment(message: Message):
    if message.successful_payment:
        set_paid(message.from_user.id)
        await message.answer("✅ Оплата получена. Безлимитный доступ активирован.")


async def main():
    if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        webhook_requests_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
        await site.start()

        webhook_url = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}/webhook"
        await bot.set_webhook(webhook_url)
        logger.info("Webhook server started: %s", webhook_url)

        await asyncio.Event().wait()
    else:
        logger.info("Starting polling...")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
