import os
from dataclasses import dataclass
import streamlit as st

@dataclass(frozen=True)
class Settings:
    model: str = "groq/openai/gpt-oss-120b"
    temperature: float = 0.2
    max_tokens: int = 6000
    request_timeout: int = 90

def groq_api_key() -> str | None:
    try:
        value = st.secrets.get("GROQ_API_KEY")
        if value:
            return value
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY")

SETTINGS = Settings()
