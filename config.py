import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения.")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не найден в переменных окружения.")

FREE_LIMIT = 5
PAID_PRICE = 3.99
CURRENCY = "USD"

CACHE_ENABLED = True
DEBUG_MODE = os.getenv("DEBUG", "False").lower() == "true"

OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "rus+eng")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", OPENAI_MODEL)
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

DB_PATH = "users.db"
