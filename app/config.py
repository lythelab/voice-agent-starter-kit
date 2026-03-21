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
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    elevenlabs_model: str = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")


settings = Settings()
