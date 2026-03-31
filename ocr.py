import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import logging
import sys
import os

# Для Windows - укажите путь к tesseract, если необходимо
if sys.platform == 'win32':
    # Раскомментируйте и укажите путь к tesseract.exe
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    pass

def extract_text(image_path, lang='rus+eng'):
    """
    Извлекает текст из изображения
    
    Args:
        image_path: путь к изображению
        lang: языки для распознавания (русский + английский по умолчанию)
    
    Returns:
        str: распознанный текст
    """
    try:
        # Проверяем существование файла
        if not os.path.exists(image_path):
            logging.error(f"Image file not found: {image_path}")
            return ""
        
        # Открываем изображение
        img = Image.open(image_path)
        
        # Оптимизация изображения для лучшего распознавания
        img = preprocess_image(img)
        
        # Распознаем текст
        text = pytesseract.image_to_string(img, lang=lang)
        
        # Очищаем текст
        text = text.strip()
        
        if not text:
            logging.warning(f"No text recognized from {image_path}")
        
        return text
        
    except Exception as e:
        logging.error(f"OCR error: {e}")
        return ""

def preprocess_image(img):
    """
    Предобработка изображения для улучшения распознавания текста
    """
    # Конвертируем в черно-белый
    if img.mode != 'L':
        img = img.convert('L')
    
    # Увеличиваем контрастность
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    
    # Увеличиваем резкость
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)
    
    # Применяем фильтр для улучшения текста
    img = img.filter(ImageFilter.SHARPEN)
    
    # Бинаризация (пороговая обработка)
    threshold = 150
    img = img.point(lambda p: p > threshold and 255)
    
    return img

# Функция для проверки установки Tesseract
def check_tesseract_installed():
    """
    Проверяет, установлен ли Tesseract OCR
    """
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False

# При импорте проверяем установку
if not check_tesseract_installed():
    logging.warning("Tesseract OCR is not installed or not found in PATH!")
    if sys.platform == 'win32':
        logging.warning("Please install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
    elif sys.platform == 'darwin':
        logging.warning("Please install Tesseract with: brew install tesseract tesseract-lang")
    else:
        logging.warning("Please install Tesseract with: sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng")