import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    daily_api_key: str = os.getenv("DAILY_API_KEY", "")
    daily_domain: str = os.getenv("DAILY_DOMAIN", "")
    daily_room_name: str = os.getenv("DAILY_ROOM_NAME", "voice-agent-dev")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))


settings = Settings()
