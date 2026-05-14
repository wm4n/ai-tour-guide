"""QAService — orchestrates STT → LLM → TTS pipeline for Q&A."""

import base64
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from tour_guide.log_events import LogEvents
from tour_guide.logging_config import log_event
from tour_guide.models.persona import PersonaConfig

logger = logging.getLogger(__name__)
from tour_guide.pipeline.sentence_splitter import StreamingSentenceBuffer
from tour_guide.prompts.builder import PromptBuilder
from tour_guide.providers.llm import LlmOpts, LlmProvider, Message
from tour_guide.providers.stt import SttProvider
from tour_guide.providers.tts import TtsOpts, TtsProvider


@dataclass
class TranscriptEvent:
    type: Literal["transcript"] = "transcript"
    text: str = ""


@dataclass
class TextEvent:
    type: Literal["text"] = "text"
    chunk: str = ""
    sentence_idx: int = 0


@dataclass
class AudioEvent:
    type: Literal["audio"] = "audio"
    chunk_b64: str = ""
    sentence_idx: int = 0


@dataclass
class EndEvent:
    type: Literal["end"] = "end"


@dataclass
class ErrorEvent:
    type: Literal["error"] = "error"
    code: str = ""
    message: str = ""
    retry_after_s: int = 0


QAEvent = TranscriptEvent | TextEvent | AudioEvent | EndEvent | ErrorEvent


class QAService:
    """Orchestrates Q&A: SttProvider → PromptBuilder.build_qa → LLM → TTS → events."""

    def __init__(self, stt: SttProvider, llm: LlmProvider, tts: TtsProvider) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts

    async def answer(
        self,
        audio_bytes: bytes,
        persona: PersonaConfig,
        lang: str,
        current_poi_name: str | None,
        narration_so_far: str,
    ) -> AsyncIterator[QAEvent]:
        """Stream Q&A events.

        Yields: TranscriptEvent → TextEvent+AudioEvent pairs → EndEvent
        """
        start = time.monotonic()
        log_event(logger, LogEvents.QA_START, poi_id=current_poi_name or "")

        # 1. STT
        user_question = await self._stt.transcribe(audio_bytes, lang)
        stt_ms = int((time.monotonic() - start) * 1000)
        log_event(logger, LogEvents.QA_STT_DONE, level="debug", duration_ms=stt_ms)
        yield TranscriptEvent(text=user_question)

        # 2. Build prompt
        raw_messages = PromptBuilder.build_qa(
            persona=persona,
            lang=lang,
            current_poi_name=current_poi_name,
            narration_so_far=narration_so_far,
            user_question=user_question,
        )
        llm_messages = [Message(role=m["role"], content=m["content"]) for m in raw_messages]

        # 3. LLM stream → sentence split → TTS
        buffer = StreamingSentenceBuffer()
        sentence_idx = 0
        voice_id = persona.voice.get(lang, "Charon")

        async for chunk in self._llm.chat_stream(llm_messages, LlmOpts()):
            sentences = buffer.feed(chunk)
            for sentence in sentences:
                yield TextEvent(chunk=sentence, sentence_idx=sentence_idx)
                audio_bytes_out = await self._synthesize_all(sentence, voice_id)
                yield AudioEvent(
                    chunk_b64=base64.b64encode(audio_bytes_out).decode(),
                    sentence_idx=sentence_idx,
                )
                sentence_idx += 1

        remainder = buffer.flush()
        if remainder:
            yield TextEvent(chunk=remainder, sentence_idx=sentence_idx)
            audio_bytes_out = await self._synthesize_all(remainder, voice_id)
            yield AudioEvent(
                chunk_b64=base64.b64encode(audio_bytes_out).decode(),
                sentence_idx=sentence_idx,
            )

        total_ms = int((time.monotonic() - start) * 1000)
        log_event(logger, LogEvents.QA_ANSWER_COMPLETE, poi_id=current_poi_name or "", duration_ms=total_ms)
        yield EndEvent()

    async def _synthesize_all(self, text: str, voice_id: str) -> bytes:
        chunks = b""
        async for audio_bytes in self._tts.synthesize(text, voice_id, TtsOpts()):
            chunks += audio_bytes
        return chunks
