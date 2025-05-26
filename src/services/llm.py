from loguru import logger
from src.core.config import settings
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# TODO: Add more models later and put them into a Enum
def summarize_doc(context: str, model: str = "gpt-4o-mini") -> str:
    system_prompt = (
        "You're an expert in API documentation. Given an OpenAPI spec, answer user questions "
        "clearly and concisely. If unsure, say you don't know."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{context}"}
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error summarizing document: {e}")
        return ""
