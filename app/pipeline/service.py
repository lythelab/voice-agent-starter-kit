from __future__ import annotations

from time import perf_counter

from app.pipeline.adapters import ASRAdapter, LLMAdapter, TTSAdapter
from app.pipeline.conversation import ConversationManager
from app.telemetry import latency_store


class AudioPipelineService:
    def __init__(self) -> None:
        self.asr = ASRAdapter()
        self.llm = LLMAdapter()
        self.tts = TTSAdapter()
        self.conversation = ConversationManager()

    async def process_audio(self, audio_bytes: bytes, mime_type: str) -> dict:
        total_start = perf_counter()

        asr_start = perf_counter()
        transcript = await self.asr.transcribe_audio(audio_bytes, mime_type)
        asr_ms = (perf_counter() - asr_start) * 1000
        if not transcript:
            transcript = "I could not detect speech. Please try again."

        self.conversation.add_user_message(transcript)

        llm_start = perf_counter()
        assistant_text = await self.llm.generate_reply(self.conversation.get_messages())
        llm_ms = (perf_counter() - llm_start) * 1000

        self.conversation.add_assistant_message(assistant_text)

        tts_start = perf_counter()
        tts_result = await self.tts.synthesize(assistant_text)
        tts_ms = (perf_counter() - tts_start) * 1000

        total_ms = (perf_counter() - total_start) * 1000

        latency_store.add("pipeline_asr_ms", asr_ms)
        latency_store.add("pipeline_llm_ms", llm_ms)
        latency_store.add("pipeline_tts_ms", tts_ms)
        latency_store.add("pipeline_total_ms", total_ms)

        payload = {
            "type": "pipeline_result",
            "transcript": transcript,
            "assistant_text": assistant_text,
            "latency_ms": {
                "asr": round(asr_ms, 2),
                "llm": round(llm_ms, 2),
                "tts": round(tts_ms, 2),
                "total": round(total_ms, 2),
            },
        }

        if tts_result is not None:
            audio_b64, audio_mime = tts_result
            payload["assistant_audio_b64"] = audio_b64
            payload["assistant_audio_mime"] = audio_mime

        return payload
