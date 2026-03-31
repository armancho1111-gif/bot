import logging
import os
import sys

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

if sys.platform == "win32":
    # При необходимости можно явно указать путь к tesseract.exe:
    # pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    pass


def extract_text(image_path, lang="rus+eng"):
    """
    Извлекает текст из изображения с помощью OCR.
    """
    try:
        if not os.path.exists(image_path):
            logging.error("Image file not found: %s", image_path)
            return ""

        img = Image.open(image_path)
        img = preprocess_image(img)

        text = pytesseract.image_to_string(img, lang=lang)
        text = text.strip()

        if not text:
            logging.warning("No text recognized from %s", image_path)

        return text

    except Exception as e:
        logging.error("OCR error: %s", e)
        return ""


def preprocess_image(img):
    """
    Предобработка изображения для улучшения OCR.
    """
    if img.width < 1800:
        scale = max(2, int(1800 / max(img.width, 1)))
        img = img.resize((img.width * scale, img.height * scale))

    if img.mode != "L":
        img = img.convert("L")

    contrast = ImageEnhance.Contrast(img)
    img = contrast.enhance(2.0)

    sharpness = ImageEnhance.Sharpness(img)
    img = sharpness.enhance(2.0)

    img = img.filter(ImageFilter.SHARPEN)

    threshold = 150
    img = img.point(lambda p: 255 if p > threshold else 0)

    return img


def check_tesseract_installed():
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


if not check_tesseract_installed():
    logging.warning("Tesseract OCR is not installed or not found in PATH.")
    if sys.platform == "win32":
        logging.warning("Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki")
    elif sys.platform == "darwin":
        logging.warning("Install Tesseract with: brew install tesseract tesseract-lang")
    else:
        logging.warning("Install Tesseract with: sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng")
