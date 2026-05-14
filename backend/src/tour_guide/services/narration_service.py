"""NarrationService — orchestrates LLM streaming, sentence splitting, and TTS synthesis."""

import base64
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from tour_guide.cache.narration_cache import NarrationCache
from tour_guide.log_events import LogEvents
from tour_guide.logging_config import log_event

logger = logging.getLogger(__name__)
from tour_guide.models.persona import PersonaConfig
from tour_guide.models.poi import POIContext
from tour_guide.pipeline.sentence_splitter import StreamingSentenceBuffer
from tour_guide.prompts.builder import PromptBuilder
from tour_guide.providers.llm import LlmOpts, LlmProvider, Message
from tour_guide.providers.tts import TtsOpts, TtsProvider
from tour_guide.services.confidence import ConfidenceClassifier

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


@dataclass
class MetaEvent:
    type: Literal["meta"] = "meta"
    poi_id: str = ""
    cache_hit: bool = False
    confidence: str = "low"
    estimated_duration_s: int = 0


@dataclass
class TextEvent:
    type: Literal["text"] = "text"
    chunk: str = ""
    sentence_idx: int = 0


@dataclass
class AudioEvent:
    type: Literal["audio"] = "audio"
    chunk_b64: str = ""  # base64-encoded audio bytes
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


NarrationEvent = MetaEvent | TextEvent | AudioEvent | EndEvent | ErrorEvent


# ---------------------------------------------------------------------------
# NarrationService
# ---------------------------------------------------------------------------


class NarrationService:
    """Orchestrates narration: PromptBuilder → LLM stream → sentence split → TTS → events."""

    def __init__(
        self,
        llm: LlmProvider,
        tts: TtsProvider,
        cache: NarrationCache | None = None,
    ) -> None:
        self._llm = llm
        self._tts = tts
        self._cache = cache

    async def narrate(
        self,
        poi: POIContext,
        persona: PersonaConfig,
        lang: str,
        length: str,
        force_regenerate: bool = False,
    ) -> AsyncIterator[NarrationEvent]:
        """Stream narration events for the given POI and persona.

        Yields:
            MetaEvent — first, with confidence and cache status
            TextEvent + AudioEvent — interleaved pairs per sentence (cache miss path)
            AudioEvent — single event with full cached audio (cache hit path)
            EndEvent — final event
        """
        confidence = ConfidenceClassifier.classify(poi)
        cache_key = f"{poi.osm.id}|{persona.id}|{lang}|{length}"
        start = time.monotonic()

        # 1. Check cache (if cache is configured and not force-regenerating)
        if self._cache is not None and not force_regenerate:
            cached = self._cache.get(cache_key)
            if cached is not None:
                cached_audio, _transcript = cached
                log_event(logger, LogEvents.NARRATION_START, poi_id=poi.osm.id, cache_hit=True)
                yield MetaEvent(
                    poi_id=poi.osm.id,
                    cache_hit=True,
                    confidence=confidence,
                )
                yield AudioEvent(
                    chunk_b64=base64.b64encode(cached_audio).decode(),
                    sentence_idx=0,
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)
                log_event(logger, LogEvents.NARRATION_COMPLETE, poi_id=poi.osm.id, duration_ms=elapsed_ms)
                yield EndEvent()
                return

        # 2. Cache miss (or no cache / force_regenerate): run full pipeline
        log_event(logger, LogEvents.NARRATION_START, poi_id=poi.osm.id, cache_hit=False)
        yield MetaEvent(
            poi_id=poi.osm.id,
            cache_hit=False,
            confidence=confidence,
        )

        # 3. Build prompt messages
        raw_messages = PromptBuilder.build(persona, poi, lang, length)
        llm_messages = [Message(role=m["role"], content=m["content"]) for m in raw_messages]
        opts = LlmOpts()

        # 4. Stream LLM → split sentences → TTS → yield events
        buffer = StreamingSentenceBuffer()
        sentence_idx = 0
        voice_id = persona.voice.get(lang, "Charon")
        all_audio_chunks: list[bytes] = []

        async for chunk in self._llm.chat_stream(llm_messages, opts):
            sentences = buffer.feed(chunk)
            for sentence in sentences:
                yield TextEvent(chunk=sentence, sentence_idx=sentence_idx)
                audio_bytes = await self._synthesize_all(sentence, voice_id)
                all_audio_chunks.append(audio_bytes)
                yield AudioEvent(
                    chunk_b64=base64.b64encode(audio_bytes).decode(),
                    sentence_idx=sentence_idx,
                )
                sentence_idx += 1

        # 5. Flush remaining buffer content
        remainder = buffer.flush()
        if remainder:
            yield TextEvent(chunk=remainder, sentence_idx=sentence_idx)
            audio_bytes = await self._synthesize_all(remainder, voice_id)
            all_audio_chunks.append(audio_bytes)
            yield AudioEvent(
                chunk_b64=base64.b64encode(audio_bytes).decode(),
                sentence_idx=sentence_idx,
            )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        log_event(logger, LogEvents.NARRATION_COMPLETE, poi_id=poi.osm.id, duration_ms=elapsed_ms)
        yield EndEvent()

        # 6. Populate cache after EndEvent (if cache is configured)
        if self._cache is not None:
            combined_audio = b"".join(all_audio_chunks)
            self._cache.put(cache_key, combined_audio, "")

    async def _synthesize_all(self, text: str, voice_id: str) -> bytes:
        """Collect all audio chunks from TTS into a single bytes object."""
        audio_chunks = b""
        async for audio_bytes in self._tts.synthesize(text, voice_id, TtsOpts()):
            audio_chunks += audio_bytes
        return audio_chunks
