from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings

DAILY_API_BASE = "https://api.daily.co/v1"


async def _daily_request(path: str, method: str = "GET", json: dict[str, Any] | None = None) -> dict[str, Any]:
    if not settings.daily_api_key:
        raise HTTPException(status_code=500, detail="DAILY_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.daily_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.request(
            method=method,
            url=f"{DAILY_API_BASE}{path}",
            headers=headers,
            json=json,
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return response.json()


async def ensure_room(room_name: str) -> dict[str, Any]:
    try:
        return await _daily_request(f"/rooms/{room_name}")
    except HTTPException as error:
        if error.status_code != 404:
            raise

    payload = {
        "name": room_name,
        "properties": {
            "exp": int(2e9),
            "enable_screenshare": False,
            "enable_chat": False,
        },
    }
    return await _daily_request("/rooms", method="POST", json=payload)


async def create_meeting_token(room_name: str, user_name: str | None = None) -> str:
    await ensure_room(room_name)
    payload = {
        "properties": {
            "room_name": room_name,
            "is_owner": True,
            "user_name": user_name or "voice-user",
            "enable_screenshare": False,
            "start_video_off": True,
            "start_audio_off": False,
        }
    }
    token_response = await _daily_request("/meeting-tokens", method="POST", json=payload)
    return token_response["token"]
