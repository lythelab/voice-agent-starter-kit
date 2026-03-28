from __future__ import annotations

import re
from time import perf_counter
from typing import AsyncIterator

from app.pipeline.adapters import ASRAdapter, LLMAdapter, TTSAdapter
from app.telemetry import latency_store


class AudioPipelineService:
    def __init__(self) -> None:
        self.asr = ASRAdapter()
        self.llm = LLMAdapter()
        self.tts = TTSAdapter()

    async def process_audio_stream(self, audio_bytes: bytes, mime_type: str) -> AsyncIterator[dict]:
        total_start = perf_counter()

        asr_start = perf_counter()
        transcript = await self.asr.transcribe_audio(audio_bytes, mime_type)
        asr_ms = (perf_counter() - asr_start) * 1000
        if not transcript:
            transcript = "I could not detect speech. Please try again."
        yield {"type": "transcript", "transcript": transcript}

        llm_start = perf_counter()
        tts_ms = 0.0
        assistant_chunks: list[str] = []
        chunk_index = 0
        tts_enabled = False
        pending_buffer = ""

        async for token in self.llm.stream_reply_tokens(transcript):
            assistant_chunks.append(token)
            pending_buffer += token
            yield {"type": "assistant_text_delta", "delta": token}

            ready_chunks, pending_buffer = self._extract_tts_ready_chunks(pending_buffer)
            for chunk in ready_chunks:
                chunk_tts_start = perf_counter()
                tts_result = await self.tts.synthesize(chunk)
                tts_ms += (perf_counter() - chunk_tts_start) * 1000
                if tts_result is None:
                    continue

                tts_enabled = True
                audio_b64, audio_mime = tts_result
                yield {
                    "type": "assistant_audio_chunk",
                    "chunk_index": chunk_index,
                    "text": chunk,
                    "audio_b64": audio_b64,
                    "audio_mime": audio_mime,
                }
                chunk_index += 1

        if pending_buffer.strip():
            final_chunk = pending_buffer.strip()
            chunk_tts_start = perf_counter()
            tts_result = await self.tts.synthesize(final_chunk)
            tts_ms += (perf_counter() - chunk_tts_start) * 1000
            if tts_result is not None:
                tts_enabled = True
                audio_b64, audio_mime = tts_result
                yield {
                    "type": "assistant_audio_chunk",
                    "chunk_index": chunk_index,
                    "text": final_chunk,
                    "audio_b64": audio_b64,
                    "audio_mime": audio_mime,
                }
                chunk_index += 1

        assistant_text = "".join(assistant_chunks).strip()
        if not assistant_text:
            assistant_text = "I did not generate a response. Please try again."
        llm_ms = (perf_counter() - llm_start) * 1000

        total_ms = (perf_counter() - total_start) * 1000

        latency_store.add("pipeline_asr_ms", asr_ms)
        latency_store.add("pipeline_llm_ms", llm_ms)
        latency_store.add("pipeline_tts_ms", tts_ms)
        latency_store.add("pipeline_total_ms", total_ms)

        yield {
            "type": "pipeline_result",
            "transcript": transcript,
            "assistant_text": assistant_text,
            "assistant_audio_streamed": tts_enabled,
            "audio_chunk_count": chunk_index,
            "latency_ms": {
                "asr": round(asr_ms, 2),
                "llm": round(llm_ms, 2),
                "tts": round(tts_ms, 2),
                "total": round(total_ms, 2),
            },
        }

    @staticmethod
    def _extract_tts_ready_chunks(buffer: str) -> tuple[list[str], str]:
        chunks: list[str] = []
        last_index = 0

        for match in re.finditer(r"[.!?]\s+|\n+", buffer):
            end = match.end()
            chunk = buffer[last_index:end].strip()
            if chunk:
                chunks.append(chunk)
            last_index = end

        if not chunks and len(buffer) >= 140:
            split_index = buffer.rfind(" ", 0, 140)
            if split_index > 0:
                chunk = buffer[:split_index].strip()
                if chunk:
                    chunks.append(chunk)
                return chunks, buffer[split_index + 1 :]

        return chunks, buffer[last_index:]
