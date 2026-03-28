from pathlib import Path
import asyncio
import sys
import base64
import json
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.pipeline import AudioPipelineService
from app.telemetry import latency_store
from app.transport.daily import create_meeting_token

app = FastAPI(title="Voice Agent Transport Layer")

static_dir = Path(__file__).resolve().parents[1] / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class TokenRequest(BaseModel):
    user_name: str | None = None


@app.middleware("http")
async def http_latency_middleware(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    elapsed_ms = (perf_counter() - start) * 1000

    metric_name = f"http_{request.method}_{request.url.path}"
    latency_store.add(metric_name, elapsed_ms)
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/latency/summary")
async def latency_summary() -> dict:
    return {"metrics": latency_store.summary()}


@app.post("/api/transport/token")
async def transport_token(payload: TokenRequest) -> dict[str, str]:
    token = await create_meeting_token(settings.daily_room_name, payload.user_name)
    room_url = f"https://{settings.daily_domain}/{settings.daily_room_name}"
    return {"token": token, "room_url": room_url}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.websocket("/ws/audio-pipeline")
async def audio_pipeline(websocket: WebSocket) -> None:
    await websocket.accept()
    pipeline_service = AudioPipelineService()
    active_task: asyncio.Task | None = None
    await websocket.send_text(json.dumps({"type": "ready"}))

    async def _run_pipeline(audio_bytes: bytes, mime_type: str) -> None:
        """Execute the pipeline and send the result back over the socket."""
        try:
            result = await pipeline_service.process_audio(audio_bytes, mime_type)
            await websocket.send_text(json.dumps(result))
        except asyncio.CancelledError:
            await websocket.send_text(
                json.dumps({"type": "info", "message": "Previous request cancelled (barge-in)"})
            )
        except Exception as exc:  # noqa: BLE001
            await websocket.send_text(json.dumps({"type": "error", "error": str(exc)}))

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            message_type = payload.get("type")

            if message_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if message_type != "user_audio":
                await websocket.send_text(
                    json.dumps({"type": "error", "error": f"Unsupported message type: {message_type}"})
                )
                continue

            audio_b64 = payload.get("audio_b64", "")
            mime_type = payload.get("mime_type", "audio/webm")
            if not audio_b64:
                await websocket.send_text(json.dumps({"type": "error", "error": "Missing audio payload"}))
                continue

            # Cancel any in-flight pipeline task (barge-in)
            if active_task and not active_task.done():
                active_task.cancel()
                try:
                    await active_task
                except asyncio.CancelledError:
                    pass

            await websocket.send_text(json.dumps({"type": "processing"}))

            audio_bytes = base64.b64decode(audio_b64)
            active_task = asyncio.create_task(_run_pipeline(audio_bytes, mime_type))
    except WebSocketDisconnect:
        if active_task and not active_task.done():
            active_task.cancel()
        return
