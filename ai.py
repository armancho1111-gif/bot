from openai import OpenAI
from config import OPENAI_API_KEY, CACHE_ENABLED
from db import get_cached_answer, set_cache

client = OpenAI(api_key=OPENAI_API_KEY)

def solve_task(text, mode="full"):
    if CACHE_ENABLED:
        cached = get_cached_answer(text, mode)
        if cached:
            return cached

    prompt = f"Реши задачу {'кратко' if mode=='answer_only' else 'и объясни простым языком'}: {text}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    answer = response.choices[0].message.content

    if CACHE_ENABLED:
        set_cache(text, answer, mode)

    return answer