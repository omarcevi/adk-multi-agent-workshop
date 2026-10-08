from google.adk.models import Gemini
from google.genai import types


def gemini(model: str) -> Gemini:
    """Gemini with retries. Under load the endpoint answers 429/503, and without a
    retry a single such answer fails the whole turn (every agent in it)."""
    return Gemini(model=model, retry_options=types.HttpRetryOptions(attempts=5, initial_delay=2))
