"""SttProvider — Speech-to-Text provider abstraction."""

import asyncio
from typing import Protocol

from google import genai


class SttProvider(Protocol):
    async def transcribe(self, audio_bytes: bytes, lang: str) -> str: ...


class FakeSttProvider:
    """Returns a scripted transcription for testing."""

    def __init__(self, scripted_text: str = "這是測試問題。"):
        self._text = scripted_text

    async def transcribe(self, audio_bytes: bytes, lang: str) -> str:
        return self._text


class GeminiSttAdapter:
    """Real STT provider using Gemini multimodal API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def transcribe(self, audio_bytes: bytes, lang: str) -> str:
        def _sync_transcribe() -> str:
            client = genai.Client(api_key=self._api_key)
            lang_hint = "繁體中文" if lang == "zh-TW" else "English"
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": "audio/wav",
                                    "data": audio_bytes,
                                }
                            },
                            {"text": f"Please transcribe this audio in {lang_hint}. Return only the transcribed text, nothing else."},
                        ]
                    }
                ],
            )
            return response.text.strip()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_transcribe)
