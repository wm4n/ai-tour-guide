import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import types as genai_types


@dataclass
class TtsOpts:
    speaking_rate: float = 1.0
    emotion: str = "neutral"


class TtsProvider(Protocol):
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        opts: TtsOpts,
    ) -> AsyncIterator[bytes]: ...


class GeminiTtsAdapter:
    """Real TTS provider using Google Gemini TTS API."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        opts: TtsOpts,
    ) -> AsyncIterator[bytes]:
        client = genai.Client(api_key=self._api_key)

        # Run sync TTS in thread pool to avoid blocking
        def _synthesize_sync():
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
                config=genai_types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=genai_types.SpeechConfig(
                        voice_config=genai_types.VoiceConfig(
                            prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                                voice_name=voice_id,
                            )
                        )
                    ),
                ),
            )
            # Extract audio bytes from response
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                    return part.inline_data.data
            return b""

        loop = asyncio.get_event_loop()
        audio_bytes = await loop.run_in_executor(None, _synthesize_sync)
        if audio_bytes:
            yield audio_bytes
