import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Токены
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Проверка наличия токенов
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не найден в переменных окружения!")

# Лимиты и цены
FREE_LIMIT = 5
PAID_PRICE = 3.99
CURRENCY = "USD"

# Настройки
CACHE_ENABLED = True
DEBUG_MODE = os.getenv("DEBUG", "False").lower() == "true"

# Настройки OCR
OCR_LANGUAGE = "rus+eng"  # Языки для распознавания

# Настройки OpenAI
OPENAI_MODEL = "gpt-3.5-turbo"  # Модель для использования
OPENAI_MAX_TOKENS = 2000
OPENAI_TEMPERATURE = 0.7

# Настройки базы данных
DB_PATH = "users.db"