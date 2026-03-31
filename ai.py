import base64
import logging
import mimetypes
import os

from openai import OpenAI

from config import (
    CACHE_ENABLED,
    OPENAI_API_KEY,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_VISION_MODEL,
)
from db import get_cached_answer, set_cache

client = OpenAI(api_key=OPENAI_API_KEY)

TASK_MISSING_MARKERS = {
    "",
    "none",
    "null",
    "nil",
    "no_task",
    "n/a",
}


def normalize_task_text(text):
    if text is None:
        return ""

    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    lowered = normalized.lower()
    if lowered in TASK_MISSING_MARKERS:
        return ""

    if "в сообщении нет самой задачи" in lowered and "none" in lowered:
        return ""

    return normalized


def _response_to_text(response):
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if text_value:
                chunks.append(text_value)

    return "\n".join(chunks).strip()


def _build_solution_prompt(text, mode):
    if mode == "answer_only":
        return (
            "Реши задачу максимально кратко. "
            "Верни только ответ или очень короткую фразу без лишних пояснений.\n\n"
            f"Задача:\n{text}"
        )

    return (
        "Реши задачу подробно и понятно, шаг за шагом. "
        "Если это математика, покажи вычисления. "
        "Если это логика, физика или другой предмет, объясни ход решения простым языком. "
        "Отвечай на русском.\n\n"
        f"Задача:\n{text}"
    )


def _image_to_data_url(image_path):
    mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def extract_task_from_image(image_path, caption=""):
    """
    Пытается извлечь условие задачи с изображения с помощью vision-модели.
    Возвращает только текст задачи без решения.
    """
    if not os.path.exists(image_path):
        logging.error("Image file not found: %s", image_path)
        return ""

    caption = normalize_task_text(caption)

    try:
        prompt = (
            "На изображении может быть школьная или учебная задача. "
            "Тебе нужно извлечь только условие задачи и переписать его аккуратно. "
            "Не решай задачу. Не добавляй комментарии, markdown, JSON и слово None. "
            "Если задача не читается или на фото нет условия, ответь только NO_TASK."
        )

        if caption:
            prompt += f"\n\nПодпись пользователя к фото:\n{caption}"

        response = client.responses.create(
            model=OPENAI_VISION_MODEL,
            instructions="Ты аккуратно читаешь задачи с изображений и возвращаешь только их текст.",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": _image_to_data_url(image_path)},
                    ],
                }
            ],
            temperature=0.1,
            max_output_tokens=800,
        )

        extracted_text = normalize_task_text(_response_to_text(response))
        if extracted_text.upper() == "NO_TASK":
            return ""

        return extracted_text

    except Exception as e:
        logging.error("Vision extraction error: %s", e)
        return ""


def solve_task(text, mode="full"):
    """
    Решает задачу с помощью OpenAI API.
    """
    text = normalize_task_text(text)
    if not text:
        return "❌ Не вижу условия задачи. Пришлите текст или более четкое фото."

    try:
        if CACHE_ENABLED:
            cached = get_cached_answer(text, mode)
            if cached:
                logging.info("Using cached answer for task: %s...", text[:50])
                return cached

        logging.info("Sending request to OpenAI for task: %s...", text[:100])

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=(
                "Ты опытный репетитор по математике и другим школьным предметам. "
                "Отвечай понятно, доброжелательно и на русском языке."
            ),
            input=_build_solution_prompt(text, mode),
            temperature=OPENAI_TEMPERATURE,
            max_output_tokens=OPENAI_MAX_TOKENS,
        )

        answer = _response_to_text(response)
        if not answer:
            raise ValueError("OpenAI вернул пустой ответ")

        if CACHE_ENABLED:
            set_cache(text, answer, mode)

        return answer

    except Exception as e:
        logging.error("Error solving task: %s", e)
        return f"❌ Ошибка при решении задачи: {str(e)}\nПопробуйте позже."


def test_solve_task():
    test_text = "Сколько будет 2+2?"
    result = solve_task(test_text, "answer_only")
    print(f"Test result: {result}")
