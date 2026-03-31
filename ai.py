from openai import OpenAI
from config import OPENAI_API_KEY, CACHE_ENABLED
from db import get_cached_answer, set_cache
import logging

client = OpenAI(api_key=OPENAI_API_KEY)

def solve_task(text, mode="full"):
    """
    Решает задачу с помощью OpenAI API
    
    Args:
        text: текст задачи
        mode: режим решения ("full" - полное объяснение, "answer_only" - только ответ)
    
    Returns:
        str: ответ на задачу
    """
    try:
        # Проверка кэша
        if CACHE_ENABLED:
            cached = get_cached_answer(text, mode)
            if cached:
                logging.info(f"Using cached answer for task: {text[:50]}...")
                return cached
        
        # Формируем промпт
        if mode == "answer_only":
            prompt = f"Реши задачу максимально кратко, дай только ответ (цифру или короткую фразу): {text}"
        else:
            prompt = f"Реши задачу подробно, объясни решение простым языком, шаг за шагом. Если это математика - покажи вычисления. Если логика - объясни ход мыслей. Задача: {text}"
        
        # Отправляем запрос к API
        logging.info(f"Sending request to OpenAI for task: {text[:100]}...")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Используем доступную модель
            messages=[
                {"role": "system", "content": "Ты - опытный репетитор по математике и другим предметам. Помогаешь решать задачи понятно и доступно."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        answer = response.choices[0].message.content
        
        # Сохраняем в кэш
        if CACHE_ENABLED:
            set_cache(text, answer, mode)
        
        return answer
        
    except Exception as e:
        logging.error(f"Error solving task: {e}")
        return f"❌ Ошибка при решении задачи: {str(e)}\nПопробуйте позже."

# Функция для тестирования
def test_solve_task():
    test_text = "Сколько будет 2+2?"
    result = solve_task(test_text, "answer_only")
    print(f"Test result: {result}")