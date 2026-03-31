import asyncio
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

async def simulate_progress(chat, bot, steps=5):
    msg = await bot.send_message(chat, "⏳ Обработка 0%")
    for i in range(1, steps+1):
        await asyncio.sleep(0.5)
        await msg.edit_text(f"⏳ Обработка {i*20}%")
    return msg

def get_repeat_buttons():
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Повторить задачу", callback_data="repeat_task")],
            [InlineKeyboardButton(text="🆕 Новая задача", callback_data="new_task")],
        ]
    )
    return markup