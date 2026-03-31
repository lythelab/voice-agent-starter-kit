from __future__ import annotations

import base64
import io
import json
import re
import wave
from typing import AsyncIterator

import httpx

from app.config import settings
from app.pipeline.tools import ToolRegistry, create_default_registry

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
    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        self.tool_registry = tool_registry or create_default_registry()

    async def stream_reply_tokens(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream LLM tokens. Tool calls are handled internally via the registry."""
        if settings.groq_api_key:
            async for token in self._groq_stream(messages, include_tools=True):
                yield token
            return

        # Fallback: yield words from a canned response
        last_user_text = messages[-1].get("content", "") if messages else ""
        fallback = (
            "I heard you. This is a fallback response because GROQ_API_KEY is not configured. "
            f"You said: {last_user_text}"
        )
        for match in re.finditer(r"\S+\s*", fallback):
            yield match.group(0)

    async def generate_reply(self, messages: list[dict[str, str]]) -> str:
        """Non-streaming convenience wrapper."""
        parts: list[str] = []
        async for token in self.stream_reply_tokens(messages):
            parts.append(token)
        return "".join(parts).strip()

    async def _groq_stream(
        self, messages: list[dict], *, include_tools: bool = True
    ) -> AsyncIterator[str]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        body: dict = {
            "model": settings.groq_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1024,
            "stream": True,
        }

        # Only attach tool schemas when the caller wants them and the registry
        # has tools.  On the follow-up call after tool execution we set
        # include_tools=False to prevent infinite recursion.
        if include_tools and self.tool_registry.has_tools():
            body["tools"] = self.tool_registry.get_schemas()
            body["tool_choice"] = "auto"

        print(f"[DEBUG] Groq request — model={body['model']}, include_tools={include_tools}, "
              f"tools_attached={'tools' in body}, tool_count={len(body.get('tools', []))}")
        print(f"[DEBUG] Messages count: {len(messages)}, last role: {messages[-1].get('role') if messages else 'N/A'}")

        client = _get_client()
        tool_calls_buffer: dict[int, dict] = {}
        content_parts: list[str] = []
        
        self._filler_fired = False

        async with client.stream("POST", url, headers=headers, json=body, timeout=45.0) as response:
            if response.status_code >= 400:
                raise RuntimeError(f"Groq error: {await response.aread()}")

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = payload.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                # --- Accumulate streamed tool-call fragments ---
                if "tool_calls" in delta:
                    print(f"[DEBUG] Received tool_call delta: {delta['tool_calls']}")
                    
                    if not getattr(self, "_filler_fired", False):
                        from app.audio_playback.fillers import play_random_filler
                        print("[DEBUG] Firing filler audio!")
                        play_random_filler()
                        self._filler_fired = True

                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": tc.get("function", {}).get("name", ""),
                                    "arguments": "",
                                },
                            }
                        if tc.get("id"):
                            tool_calls_buffer[idx]["id"] = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            tool_calls_buffer[idx]["function"]["name"] = fn["name"]
                        if fn.get("arguments"):
                            tool_calls_buffer[idx]["function"]["arguments"] += fn["arguments"]

                # --- Yield regular content tokens ---
                else:
                    token = delta.get("content")
                    if token:
                        content_parts.append(token)
                        yield token

        # -----------------------------------------------------------------
        # Tool-call feedback loop
        # If the LLM requested tool calls, execute them via the registry,
        # feed the results back, and stream the LLM's natural-language reply.
        # -----------------------------------------------------------------
        if not tool_calls_buffer:
            print("[DEBUG] No tool calls detected — LLM replied with text only.")
            return

        print(f"[DEBUG] Tool calls detected: {[tool_calls_buffer[i]['function']['name'] for i in sorted(tool_calls_buffer)]}")

        tool_calls_list = [tool_calls_buffer[i] for i in sorted(tool_calls_buffer)]

        # Build follow-up messages: original + assistant + tool results
        follow_up = list(messages)
        follow_up.append({
            "role": "assistant",
            "content": "".join(content_parts) if content_parts else None,
            "tool_calls": tool_calls_list,
        })

        for tc in tool_calls_list:
            func_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            result = await self.tool_registry.execute(func_name, args)
            follow_up.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": func_name,
                "content": result,
            })

        # Second streaming call — tools disabled to prevent recursion
        async for token in self._groq_stream(follow_up, include_tools=False):
            yield token


class TTSAdapter:
    def __init__(self):
        # Add filler words for more realistic speech
        self.filler_words = [
            "um", "uh", "well", "so", "actually", "basically", 
            "let's see", "you know", "kind of", "sort of", "right"
        ]
        # Percentage chance of adding a filler word/sentence (0-100)
        self.filler_probability = 15  # 15% chance

    async def synthesize(self, text: str) -> tuple[str, str] | None:
        if not text:
            return None
        if settings.cartesia_api_key and settings.cartesia_voice_id:
            return await self._cartesia_synthesize(text)
        return None

    async def synthesize_with_fillers(self, text: str) -> tuple[str, str] | None:
        """Synthesize text with occasional filler words for realism."""
        import random
        
        # Randomly decide whether to add fillers based on probability
        if random.randint(1, 100) <= self.filler_probability:
            # Add a random filler at the beginning sometimes
            if random.choice([True, False]):
                filler = random.choice(self.filler_words)
                text = f"{filler}, {text}"
            # Or add fillers within the sentence
            else:
                words = text.split()
                # Add a filler approximately every 5-10 words
                for i in range(len(words)//7, 0, -1):
                    insert_pos = min(i * 7, len(words)-1)
                    if random.randint(1, 100) <= 50:  # 50% chance for each insertion point
                        filler = random.choice(self.filler_words)
                        words.insert(insert_pos, filler)
                text = " ".join(words)
        
        return await self.synthesize(text)

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