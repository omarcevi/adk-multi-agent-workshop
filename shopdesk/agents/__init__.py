from google.adk.models import Gemini
from google.genai import types


def gemini(model: str) -> Gemini:
    """Gemini that neither hangs nor gives up on the first error. Under load the
    endpoint answers 429/503, or stalls for minutes. X-Server-Timeout makes it give
    up after 45 s with a 504, and 429/503/504 are retried (4 attempts in total).
    The 60 s client timeout is only a backstop."""
    return Gemini(model=model, client_kwargs={"http_options": types.HttpOptions(
        timeout=60_000,
        headers={"X-Server-Timeout": "45"},
        retry_options=types.HttpRetryOptions(attempts=4, initial_delay=2),
    )})
