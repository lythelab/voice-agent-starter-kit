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
    sonic3_api_key: str = os.getenv("SONIC3_API_KEY", "")
    sonic3_base_url: str = os.getenv("SONIC3_BASE_URL", "https://api.smallest.ai/waves/v1")
    sonic3_model: str = os.getenv("SONIC3_MODEL", "lightning-v3.1")
    sonic3_voice_id: str = os.getenv("SONIC3_VOICE_ID", "magnus")
    sonic3_sample_rate: int = int(os.getenv("SONIC3_SAMPLE_RATE", "24000"))
    sonic3_speed: float = float(os.getenv("SONIC3_SPEED", "1.0"))
    sonic3_language: str = os.getenv("SONIC3_LANGUAGE", "en")
    sonic3_output_format: str = os.getenv("SONIC3_OUTPUT_FORMAT", "wav")


settings = Settings()
