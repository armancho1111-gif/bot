import asyncio
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

async def simulate_progress(chat_id, bot, steps=5):
    """
    Симулирует прогресс обработки
    """
    try:
        msg = await bot.send_message(chat_id, "⏳ Обработка 0%")
        
        for i in range(1, steps + 1):
            await asyncio.sleep(0.5)  # Пауза между обновлениями
            percent = i * (100 // steps)
            
            # Разные иконки в зависимости от прогресса
            if percent < 30:
                icon = "🔍"
            elif percent < 70:
                icon = "⚙️"
            else:
                icon = "✅"
            
            await msg.edit_text(f"{icon} Обработка {percent}%")
        
        await msg.edit_text("🎯 Готово! Формирую ответ...")
        return msg
        
    except Exception as e:
        # Если не удалось обновить сообщение, создаем новое
        return await bot.send_message(chat_id, "🤔 Решаю задачу...")

def get_repeat_buttons():
    """
    Возвращает кнопки для повторения задачи
    """
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Повторить задачу", callback_data="repeat_task"),
                InlineKeyboardButton(text="🆕 Новая задача", callback_data="new_task")
            ],
            [
                InlineKeyboardButton(text="📜 История", callback_data="view_history"),
                InlineKeyboardButton(text="💰 Купить доступ", callback_data="buy_access")
            ]
        ]
    )
    return markup

def get_mode_buttons():
    """
    Возвращает кнопки выбора режима
    """
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Только ответ", callback_data="mode_answer")],
            [InlineKeyboardButton(text="📖 Пошаговое объяснение", callback_data="mode_full")],
        ]
    )
    return markup