import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    daily_api_key: str = os.getenv("DAILY_API_KEY", "")
    daily_domain: str = os.getenv("DAILY_DOMAIN", "")
    daily_room_name: str = os.getenv("DAILY_ROOM_NAME", "voice-agent-dev")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    system_prompt: str = os.getenv(
        "SYSTEM_PROMPT",
        "You are a concise, helpful real-time voice assistant.",
    )
    cartesia_api_key: str = os.getenv("CARTESIA_API_KEY", "")
    cartesia_base_url: str = os.getenv("CARTESIA_BASE_URL", "https://api.cartesia.ai")
    cartesia_version: str = os.getenv("CARTESIA_VERSION", "2025-04-16")
    cartesia_model_id: str = os.getenv("CARTESIA_MODEL_ID", "sonic-3")
    cartesia_voice_id: str = os.getenv("CARTESIA_VOICE_ID", "")
    cartesia_language: str = os.getenv("CARTESIA_LANGUAGE", "en")
    cartesia_sample_rate: int = int(os.getenv("CARTESIA_SAMPLE_RATE", "24000"))
    cartesia_output_format: str = os.getenv("CARTESIA_OUTPUT_FORMAT", "wav")
    cartesia_speed: float = float(os.getenv("CARTESIA_SPEED", "1.0"))


settings = Settings()
