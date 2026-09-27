import re
from config.settings import groq_api_key

def get_groq_key():
    return groq_api_key()

def safe_text(exc: Exception) -> str:
    msg = str(exc)
    msg = re.sub(r"gsk_[A-Za-z0-9_-]+", "[REDACTED]", msg)
    return f"The operation could not be completed safely. Details: {msg[:900]}"
