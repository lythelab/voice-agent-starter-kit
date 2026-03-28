from __future__ import annotations

import base64
import io
import json
import wave

import httpx

from app.config import settings

# Persistent HTTP client — reuses TCP+TLS connections across requests.
# Eliminates ~500-1500ms of TLS handshake overhead per API call.
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


def pcm16le_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


class ASRAdapter:
    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        if settings.deepgram_api_key:
            return await self._deepgram_transcribe(audio_bytes, mime_type)
        kb = max(1, len(audio_bytes) // 1024)
        return f"Received audio ({kb} KB). Set DEEPGRAM_API_KEY for real transcription."

    async def _deepgram_transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        url = "https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true"
        payload = audio_bytes
        content_type = mime_type

        if mime_type == "audio/pcm16":
            payload = pcm16le_to_wav_bytes(audio_bytes)
            content_type = "audio/wav"

        headers = {
            "Authorization": f"Token {settings.deepgram_api_key}",
            "Content-Type": content_type,
        }

        client = _get_client()
        response = await client.post(url, headers=headers, content=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"Deepgram error: {response.text}")

        data = response.json()
        transcript = (
            data.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
            .strip()
        )
        if not transcript:
            transcript = ""
        return transcript


class LLMAdapter:
    async def generate_reply(self, messages: list[dict[str, str]]) -> str:
        if settings.groq_api_key:
            return await self._groq_reply(messages)

        last_user_text = messages[-1].get("content", "") if messages else ""
        return (
            "I heard you. This is a fallback response because GROQ_API_KEY is not configured. "
            f"You said: {last_user_text}"
        )

    async def _groq_reply(self, messages: list[dict[str, str]]) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.groq_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 150,
        }

        client = _get_client()
        response = await client.post(url, headers=headers, json=body)

        if response.status_code >= 400:
            raise RuntimeError(f"Groq error: {response.text}")

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "").strip()


class TTSAdapter:
    async def synthesize(self, text: str) -> tuple[str, str] | None:
        if not text:
            return None
        if settings.cartesia_api_key and settings.cartesia_voice_id:
            return await self._cartesia_synthesize(text)
        return None

    async def _cartesia_synthesize(self, text: str) -> tuple[str, str]:
        url = f"{settings.cartesia_base_url}/tts/bytes"
        headers = {
            "Authorization": f"Bearer {settings.cartesia_api_key}",
            "Cartesia-Version": settings.cartesia_version,
            "Content-Type": "application/json",
        }

        output_format = settings.cartesia_output_format.lower()
        if output_format == "mp3":
            output_format_payload = {
                "container": "mp3",
                "sample_rate": settings.cartesia_sample_rate,
                "bit_rate": 128000,
            }
            output_mime = "audio/mpeg"
        else:
            output_format_payload = {
                "container": "wav",
                "encoding": "pcm_f32le",
                "sample_rate": settings.cartesia_sample_rate,
            }
            output_mime = "audio/wav"

        payload = {
            "model_id": settings.cartesia_model_id,
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": settings.cartesia_voice_id,
            },
            "output_format": output_format_payload,
            "language": settings.cartesia_language,
            "generation_config": {
                "speed": settings.cartesia_speed,
            },
        }

        client = _get_client()
        response = await client.post(url, headers=headers, json=payload, timeout=45.0)

        if response.status_code >= 400:
            raise RuntimeError(f"Cartesia error: {response.text}")

        audio_b64 = base64.b64encode(response.content).decode("utf-8")
        return audio_b64, output_mime


def safe_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)
