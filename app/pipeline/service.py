from __future__ import annotations

from app.pipeline.adapters import ASRAdapter, LLMAdapter, TTSAdapter


class AudioPipelineService:
    def __init__(self) -> None:
        self.asr = ASRAdapter()
        self.llm = LLMAdapter()
        self.tts = TTSAdapter()

    async def process_audio(self, audio_bytes: bytes, mime_type: str) -> dict:
        transcript = await self.asr.transcribe_audio(audio_bytes, mime_type)
        if not transcript:
            transcript = "I could not detect speech. Please try again."

        assistant_text = await self.llm.generate_reply(transcript)
        tts_result = await self.tts.synthesize(assistant_text)

        payload = {
            "type": "pipeline_result",
            "transcript": transcript,
            "assistant_text": assistant_text,
        }

        if tts_result is not None:
            audio_b64, audio_mime = tts_result
            payload["assistant_audio_b64"] = audio_b64
            payload["assistant_audio_mime"] = audio_mime

        return payload
