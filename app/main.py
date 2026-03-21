from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.transport.daily import create_meeting_token

app = FastAPI(title="Voice Agent Transport Layer")

static_dir = Path(__file__).resolve().parents[1] / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class TokenRequest(BaseModel):
    user_name: str | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/transport/token")
async def transport_token(payload: TokenRequest) -> dict[str, str]:
    token = await create_meeting_token(settings.daily_room_name, payload.user_name)
    room_url = f"https://{settings.daily_domain}/{settings.daily_room_name}"
    return {"token": token, "room_url": room_url}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")
