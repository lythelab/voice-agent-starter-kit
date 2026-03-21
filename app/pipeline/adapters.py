from __future__ import annotations

import base64
import io
import json
import wave

import httpx

from app.config import settings


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

        async with httpx.AsyncClient(timeout=30.0) as client:
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
    async def generate_reply(self, user_text: str) -> str:
        if settings.groq_api_key:
            return await self._groq_reply(user_text)

        return (
            "I heard you. This is a fallback response because GROQ_API_KEY is not configured. "
            f"You said: {user_text}"
        )

    async def _groq_reply(self, user_text: str) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.groq_model,
            "messages": [
                {"role": "system", "content": settings.system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
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
        if settings.elevenlabs_api_key and settings.elevenlabs_voice_id:
            return await self._elevenlabs_synthesize(text)
        return None

    async def _elevenlabs_synthesize(self, text: str) -> tuple[str, str]:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
        headers = {
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": settings.elevenlabs_model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"ElevenLabs error: {response.text}")

        audio_b64 = base64.b64encode(response.content).decode("utf-8")
        return audio_b64, "audio/mpeg"


def safe_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)
