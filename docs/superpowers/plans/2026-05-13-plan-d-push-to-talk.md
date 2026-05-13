# Plan D — Push-to-talk Q&A 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI Tour Guide App 新增 Push-to-talk Q&A：長按 MapScreen 麥克風按鈕錄音，後端 STT → LLM → TTS 串流回答，旁白 duck 50% 不暫停。

**Architecture:** Backend 新增 `SttProvider`、`QAService`、`/qa` SSE endpoint；Flutter 新增 `MicRecorderService`、`QaNotifier`、`PushToTalkButton`；旁白 AudioPlayer 新增 duck/unduck；Q&A 使用獨立第二個 AudioPlayer 實例。

**Tech Stack:** Python/FastAPI/google-genai（STT）、Dart/Flutter/Riverpod、`record ^5.0`（麥克風錄音）、just_audio（已有）

---

## 檔案結構

**Backend 新增：**
- `backend/src/tour_guide/providers/stt.py` — SttProvider Protocol + GeminiSttAdapter + FakeSttProvider
- `backend/src/tour_guide/services/qa_service.py` — QAService (STT→LLM→TTS pipeline)
- `backend/src/tour_guide/api/qa.py` — POST /qa SSE endpoint
- `backend/tests/unit/test_qa_service.py`
- `backend/tests/integration/test_qa_api.py`

**Backend 修改：**
- `backend/src/tour_guide/prompts/builder.py` — 新增 `build_qa()` static method
- `backend/src/tour_guide/main.py` — wire QAService + qa router
- `backend/tests/unit/test_prompt_builder.py` — 新增 build_qa 測試

**Flutter 新增：**
- `flutter_app/lib/shared/mic/mic_recorder_service.dart`
- `flutter_app/lib/shared/backend/models/qa_event.dart`
- `flutter_app/lib/features/qa/providers/qa_provider.dart`
- `flutter_app/lib/features/qa/widgets/push_to_talk_button.dart`
- `flutter_app/test/unit/qa_provider_test.dart`
- `flutter_app/test/widget/push_to_talk_button_test.dart`

**Flutter 修改：**
- `flutter_app/pubspec.yaml` — 新增 `record: ^5.0.0`
- `flutter_app/lib/shared/audio/audio_player_service.dart` — 新增 duck/unduck
- `flutter_app/lib/shared/backend/backend_client.dart` — 新增 qa()
- `flutter_app/lib/shared/providers.dart` — 新增 micRecorderProvider + qaAudioPlayerProvider
- `flutter_app/lib/features/map/screens/map_screen.dart` — 整合 PushToTalkButton
- `flutter_app/lib/features/narration/widgets/narration_sheet.dart` — Q&A 字幕顯示

---

## Task 1：Backend — SttProvider（abstract + Fake + Gemini real）

**Files:**
- Create: `backend/src/tour_guide/providers/stt.py`
- Modify: `backend/src/tour_guide/providers/fakes.py`
- Test: `backend/tests/unit/test_stt_provider.py`

- [ ] **Step 1: 建立 `stt.py`**

```python
# backend/src/tour_guide/providers/stt.py
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
```

- [ ] **Step 2: 新增 `FakeSttProvider` 到 fakes.py**

在 `backend/src/tour_guide/providers/fakes.py` 末尾新增：

```python
from tour_guide.providers.stt import FakeSttProvider

__all__ = ["FakeLlmProvider", "FakeTtsProvider", "FakeSttProvider"]
```

> 注意：`FakeSttProvider` 已定義在 `stt.py`，這裡只是重新匯出

- [ ] **Step 3: 寫測試**

```python
# backend/tests/unit/test_stt_provider.py
"""Unit tests for FakeSttProvider."""

import pytest

from tour_guide.providers.stt import FakeSttProvider


class TestFakeSttProvider:
    @pytest.mark.asyncio
    async def test_returns_scripted_text(self):
        stt = FakeSttProvider("這是故宮博物院嗎？")
        result = await stt.transcribe(b"\x00" * 100, "zh-TW")
        assert result == "這是故宮博物院嗎？"

    @pytest.mark.asyncio
    async def test_default_text(self):
        stt = FakeSttProvider()
        result = await stt.transcribe(b"\x00" * 100, "en")
        assert isinstance(result, str)
        assert len(result) > 0
```

- [ ] **Step 4: 執行測試（確認通過）**

```bash
cd backend && .venv/bin/pytest tests/unit/test_stt_provider.py -v
```

預期：2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/providers/stt.py backend/src/tour_guide/providers/fakes.py backend/tests/unit/test_stt_provider.py
git commit -m "feat(backend): add SttProvider protocol with FakeSttProvider and GeminiSttAdapter"
```

---

## Task 2：Backend — PromptBuilder.build_qa()

**Files:**
- Modify: `backend/src/tour_guide/prompts/builder.py`
- Modify: `backend/tests/unit/test_prompt_builder.py`

- [ ] **Step 1: 先寫失敗測試**

在 `backend/tests/unit/test_prompt_builder.py` 末尾新增（在最後一個測試 class 之後）：

```python
class TestPromptBuilderQA:
    """Tests for PromptBuilder.build_qa()."""

    @pytest.fixture
    def persona(self):
        from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
        return PersonaConfig(
            id="history_uncle",
            display_name={"zh-TW": "歷史大叔"},
            voice={"zh-TW": "Charon"},
            voice_style=VoiceStyle(),
            style_profile=StyleProfile(),
            poi_source="osm_wikipedia",
            system_prompt={"zh-TW": "你是歷史大叔。"},
            narration_template={"zh-TW": "narrate {poi_name}"},
            qa_template={
                "zh-TW": "{system_prompt}\n使用者在「{poi_name}」附近，旁白摘要：{narration_summary}\n使用者問：「{user_question}」",
                "en": "{system_prompt}\nUser is near '{poi_name}'. Summary: {narration_summary}\nQuestion: '{user_question}'",
            },
        )

    def test_build_qa_with_poi(self, persona):
        messages = PromptBuilder.build_qa(
            persona=persona,
            lang="zh-TW",
            current_poi_name="故宮博物院",
            narration_so_far="故宮是台灣最重要的博物館...",
            user_question="這裡有多少文物？",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "歷史大叔" in messages[0]["content"]
        user_msg = messages[1]["content"]
        assert "故宮博物院" in user_msg
        assert "這裡有多少文物？" in user_msg

    def test_build_qa_without_poi(self, persona):
        messages = PromptBuilder.build_qa(
            persona=persona,
            lang="zh-TW",
            current_poi_name=None,
            narration_so_far="",
            user_question="台北有什麼好玩的？",
        )
        assert len(messages) == 2
        user_msg = messages[1]["content"]
        assert "台北有什麼好玩的？" in user_msg

    def test_build_qa_english(self, persona):
        messages = PromptBuilder.build_qa(
            persona=persona,
            lang="en",
            current_poi_name="National Palace Museum",
            narration_so_far="The museum holds...",
            user_question="How old is it?",
        )
        assert "How old is it?" in messages[1]["content"]
```

- [ ] **Step 2: 執行（確認失敗）**

```bash
cd backend && .venv/bin/pytest tests/unit/test_prompt_builder.py::TestPromptBuilderQA -v
```

預期：FAIL（AttributeError: type object 'PromptBuilder' has no attribute 'build_qa'）

- [ ] **Step 3: 實作 `build_qa()`**

在 `backend/src/tour_guide/prompts/builder.py` 的 `PromptBuilder` class 中，`build()` 方法之後新增：

```python
    @staticmethod
    def build_qa(
        persona: PersonaConfig,
        lang: str,
        current_poi_name: str | None,
        narration_so_far: str,
        user_question: str,
    ) -> list[dict]:
        """Build messages for Q&A LLM prompt.

        Args:
            persona: PersonaConfig with system_prompt and qa_template
            lang: Language code (e.g. "zh-TW", "en")
            current_poi_name: Name of current POI, or None if no narration active
            narration_so_far: Accumulated narration subtitle text
            user_question: Transcribed user question

        Returns:
            List of message dicts with system and user messages.
        """
        system_prompt_text = persona.system_prompt.get(lang, "")
        qa_template_text = persona.qa_template.get(lang, "")

        poi_name = current_poi_name or ("" if lang != "zh-TW" else "")

        if current_poi_name:
            user_prompt_text = qa_template_text.format(
                system_prompt=system_prompt_text,
                poi_name=poi_name,
                narration_summary=narration_so_far[:500] if narration_so_far else "(無旁白摘要)",
                user_question=user_question,
            )
        else:
            # No POI context — general Q&A
            general_prompt = (
                f"{system_prompt_text}\n使用者沒有特定景點，請以你的口吻自然回答：「{user_question}」"
                if lang == "zh-TW"
                else f"{system_prompt_text}\nUser asks without a specific POI context: '{user_question}'"
            )
            user_prompt_text = general_prompt

        return [
            {"role": "system", "content": system_prompt_text},
            {"role": "user", "content": user_prompt_text},
        ]
```

- [ ] **Step 4: 執行（確認通過）**

```bash
cd backend && .venv/bin/pytest tests/unit/test_prompt_builder.py -v
```

預期：全部通過

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/prompts/builder.py backend/tests/unit/test_prompt_builder.py
git commit -m "feat(backend): add PromptBuilder.build_qa() with poi/no-poi branches"
```

---

## Task 3：Backend — QAService（TDD）

**Files:**
- Create: `backend/src/tour_guide/services/qa_service.py`
- Create: `backend/tests/unit/test_qa_service.py`

- [ ] **Step 1: 先寫失敗測試**

```python
# backend/tests/unit/test_qa_service.py
"""Unit tests for QAService."""

import pytest

from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.providers.fakes import FakeLlmProvider, FakeTtsProvider
from tour_guide.providers.stt import FakeSttProvider
from tour_guide.services.qa_service import QAService, TranscriptEvent


def _make_persona() -> PersonaConfig:
    return PersonaConfig(
        id="history_uncle",
        display_name={"zh-TW": "歷史大叔"},
        voice={"zh-TW": "Charon"},
        voice_style=VoiceStyle(),
        style_profile=StyleProfile(),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是歷史大叔。"},
        narration_template={"zh-TW": "narrate {poi_name}"},
        qa_template={
            "zh-TW": "{system_prompt}\n{poi_name}\n{narration_summary}\n{user_question}",
        },
    )


class TestQAServiceEventOrder:
    @pytest.mark.asyncio
    async def test_first_event_is_transcript(self):
        stt = FakeSttProvider("這裡有多少文物？")
        llm = FakeLlmProvider(["故宮有約七十萬件文物。"])
        tts = FakeTtsProvider()
        service = QAService(stt=stt, llm=llm, tts=tts)

        events = []
        async for event in service.answer(
            audio_bytes=b"\x00" * 100,
            persona=_make_persona(),
            lang="zh-TW",
            current_poi_name="故宮博物院",
            narration_so_far="故宮是台灣最重要的博物館。",
        ):
            events.append(event)

        assert len(events) > 0
        assert isinstance(events[0], TranscriptEvent)
        assert events[0].text == "這裡有多少文物？"

    @pytest.mark.asyncio
    async def test_last_event_is_end(self):
        from tour_guide.services.qa_service import EndEvent
        stt = FakeSttProvider("問題")
        llm = FakeLlmProvider(["回答。"])
        tts = FakeTtsProvider()
        service = QAService(stt=stt, llm=llm, tts=tts)

        events = []
        async for event in service.answer(
            audio_bytes=b"\x00" * 100,
            persona=_make_persona(),
            lang="zh-TW",
            current_poi_name=None,
            narration_so_far="",
        ):
            events.append(event)

        assert isinstance(events[-1], EndEvent)

    @pytest.mark.asyncio
    async def test_audio_events_are_present(self):
        from tour_guide.services.qa_service import AudioEvent
        stt = FakeSttProvider("問題")
        llm = FakeLlmProvider(["回答一。回答二。"])
        tts = FakeTtsProvider()
        service = QAService(stt=stt, llm=llm, tts=tts)

        events = []
        async for event in service.answer(
            audio_bytes=b"\x00" * 100,
            persona=_make_persona(),
            lang="zh-TW",
            current_poi_name="故宮",
            narration_so_far="",
        ):
            events.append(event)

        audio_events = [e for e in events if isinstance(e, AudioEvent)]
        assert len(audio_events) > 0
```

- [ ] **Step 2: 執行（確認失敗）**

```bash
cd backend && .venv/bin/pytest tests/unit/test_qa_service.py -v
```

預期：FAIL（ModuleNotFoundError: No module named 'tour_guide.services.qa_service'）

- [ ] **Step 3: 實作 QAService**

```python
# backend/src/tour_guide/services/qa_service.py
"""QAService — orchestrates STT → LLM → TTS pipeline for Q&A."""

import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from tour_guide.models.persona import PersonaConfig
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
        # 1. STT
        user_question = await self._stt.transcribe(audio_bytes, lang)
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

        yield EndEvent()

    async def _synthesize_all(self, text: str, voice_id: str) -> bytes:
        chunks = b""
        async for audio_bytes in self._tts.synthesize(text, voice_id, TtsOpts()):
            chunks += audio_bytes
        return chunks
```

- [ ] **Step 4: 執行（確認通過）**

```bash
cd backend && .venv/bin/pytest tests/unit/test_qa_service.py -v
```

預期：3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/qa_service.py backend/tests/unit/test_qa_service.py
git commit -m "feat(backend): add QAService with STT→LLM→TTS pipeline (TDD)"
```

---

## Task 4：Backend — /qa Endpoint + Integration Test

**Files:**
- Create: `backend/src/tour_guide/api/qa.py`
- Create: `backend/tests/integration/test_qa_api.py`

- [ ] **Step 1: 先寫整合測試**

```python
# backend/tests/integration/test_qa_api.py
"""Integration tests for POST /qa SSE endpoint."""

import base64
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tour_guide.api.qa import get_persona_registry, get_qa_service, router
from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.providers.fakes import FakeLlmProvider, FakeTtsProvider
from tour_guide.providers.stt import FakeSttProvider
from tour_guide.services.qa_service import QAService


def parse_sse_events(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        if not block:
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if event_type and data is not None:
            events.append({"type": event_type, **data})
    return events


_FAKE_REGISTRY: dict = {
    "history_uncle": PersonaConfig(
        id="history_uncle",
        display_name={"zh-TW": "歷史大叔"},
        voice={"zh-TW": "Charon"},
        voice_style=VoiceStyle(),
        style_profile=StyleProfile(),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是歷史大叔。"},
        narration_template={"zh-TW": "narrate {poi_name}"},
        qa_template={
            "zh-TW": "{system_prompt}\n{poi_name}\n{narration_summary}\n{user_question}",
        },
    ),
}


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(router)
    qa_svc = QAService(
        stt=FakeSttProvider("這裡有多少文物？"),
        llm=FakeLlmProvider(["故宮有約七十萬件文物。"]),
        tts=FakeTtsProvider(),
    )
    application.dependency_overrides[get_qa_service] = lambda: qa_svc
    application.dependency_overrides[get_persona_registry] = lambda: _FAKE_REGISTRY
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def _post_qa(client, persona="history_uncle", poi_id="osm:1"):
    audio_bytes = b"\x00" * 100
    context = json.dumps({
        "current_poi_id": poi_id,
        "persona": persona,
        "lang": "zh-TW",
        "narration_so_far": "故宮是台灣最重要的博物館。",
    })
    return client.post(
        "/qa",
        files={"audio": ("recording.wav", audio_bytes, "audio/wav")},
        data={"context": context},
    )


class TestQAAPIStreamOrder:
    def test_first_event_is_transcript(self, client):
        response = _post_qa(client)
        assert response.status_code == 200
        events = parse_sse_events(response.text)
        assert events[0]["type"] == "transcript"
        assert "text" in events[0]

    def test_last_event_is_end(self, client):
        response = _post_qa(client)
        events = parse_sse_events(response.text)
        assert events[-1]["type"] == "end"

    def test_audio_event_has_chunk_b64(self, client):
        response = _post_qa(client)
        events = parse_sse_events(response.text)
        audio = next((e for e in events if e["type"] == "audio"), None)
        assert audio is not None
        assert len(audio["chunk_b64"]) > 0


class TestQAAPIValidation:
    def test_unknown_persona_returns_400(self, client):
        audio_bytes = b"\x00" * 100
        context = json.dumps({
            "current_poi_id": "osm:1",
            "persona": "unknown_persona",
            "lang": "zh-TW",
            "narration_so_far": "",
        })
        response = client.post(
            "/qa",
            files={"audio": ("recording.wav", audio_bytes, "audio/wav")},
            data={"context": context},
        )
        assert response.status_code == 400

    def test_missing_audio_returns_422(self, client):
        context = json.dumps({"persona": "history_uncle", "lang": "zh-TW", "narration_so_far": ""})
        response = client.post("/qa", data={"context": context})
        assert response.status_code == 422
```

- [ ] **Step 2: 執行（確認失敗）**

```bash
cd backend && .venv/bin/pytest tests/integration/test_qa_api.py -v
```

預期：FAIL（ModuleNotFoundError: No module named 'tour_guide.api.qa'）

- [ ] **Step 3: 實作 /qa endpoint**

```python
# backend/src/tour_guide/api/qa.py
"""POST /qa — SSE streaming Q&A endpoint."""

import dataclasses
import json

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from tour_guide.api.sse import encode_event
from tour_guide.models.persona import PersonaConfig
from tour_guide.services.qa_service import QAService

router = APIRouter()


def get_qa_service() -> QAService:
    raise NotImplementedError("Override with dependency")


def get_persona_registry() -> dict[str, PersonaConfig]:
    raise NotImplementedError("Override with dependency")


def _event_to_dict(event) -> dict:
    d = dataclasses.asdict(event)
    d.pop("type", None)
    return d


@router.post("/qa")
async def qa_answer(
    audio: UploadFile,
    context: str = Form(...),
    qa_service: QAService = Depends(get_qa_service),  # noqa: B008
    persona_registry: dict = Depends(get_persona_registry),  # noqa: B008
):
    ctx = json.loads(context)
    persona_id = ctx.get("persona", "history_uncle")

    if persona_id not in persona_registry:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown persona: '{persona_id}'. Valid options: {sorted(persona_registry.keys())}",
        )

    persona: PersonaConfig = persona_registry[persona_id]
    lang = ctx.get("lang", "zh-TW")
    current_poi_id = ctx.get("current_poi_id")  # nullable
    narration_so_far = ctx.get("narration_so_far", "")

    # Resolve POI name from ID for the prompt (use ID as name if no lookup)
    current_poi_name = current_poi_id if current_poi_id else None

    audio_bytes = await audio.read()

    async def generate():
        try:
            async for event in qa_service.answer(
                audio_bytes=audio_bytes,
                persona=persona,
                lang=lang,
                current_poi_name=current_poi_name,
                narration_so_far=narration_so_far,
            ):
                event_type = event.type
                data = _event_to_dict(event)
                yield encode_event(event_type, data)
        except Exception as e:
            yield encode_event(
                "error",
                {"code": "internal_error", "message": str(e), "retry_after_s": 0},
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: 執行（確認通過）**

```bash
cd backend && .venv/bin/pytest tests/integration/test_qa_api.py -v
```

預期：全部通過

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/api/qa.py backend/tests/integration/test_qa_api.py
git commit -m "feat(backend): add POST /qa SSE endpoint (TDD)"
```

---

## Task 5：Backend — Wire QAService in main.py

**Files:**
- Modify: `backend/src/tour_guide/main.py`
- Modify: `backend/src/tour_guide/api/__init__.py`（若需要）

- [ ] **Step 1: 更新 `main.py`**

在 `backend/src/tour_guide/main.py` 中，以下為完整替換後的內容：

```python
"""FastAPI application factory with full dependency injection wiring."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from tour_guide.api import health, narration, poi, qa
from tour_guide.cache.narration_cache import NarrationCache
from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.overpass import OverpassClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.config import AppConfig
from tour_guide.prompts.loader import PersonaLoader
from tour_guide.providers.llm import LiteLLMAdapter
from tour_guide.providers.stt import GeminiSttAdapter
from tour_guide.providers.tts import GeminiTtsAdapter
from tour_guide.services.narration_service import NarrationService
from tour_guide.services.poi_service import POIService
from tour_guide.services.qa_service import QAService


def create_app(config: AppConfig) -> FastAPI:
    http_client = httpx.AsyncClient()

    overpass_client = OverpassClient(client=http_client)
    wikipedia_client = WikipediaClient(client=http_client)
    poi_cache = POICache(config.poi_cache_dir)
    narration_cache = NarrationCache(config.narration_cache_dir)

    llm_provider = LiteLLMAdapter(api_key=config.gemini_api_key)
    tts_provider = GeminiTtsAdapter(api_key=config.gemini_api_key)
    stt_provider = GeminiSttAdapter(api_key=config.gemini_api_key)

    poi_service = POIService(
        overpass=overpass_client,
        wikipedia=wikipedia_client,
        cache=poi_cache,
    )
    narration_service = NarrationService(
        llm=llm_provider,
        tts=tts_provider,
        cache=narration_cache,
    )
    qa_service = QAService(
        stt=stt_provider,
        llm=llm_provider,
        tts=tts_provider,
    )
    persona_registry = PersonaLoader.load_all()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await http_client.aclose()

    app = FastAPI(title="AI Tour Guide", lifespan=lifespan)

    app.dependency_overrides[poi.get_poi_service] = lambda: poi_service
    app.dependency_overrides[narration.get_narration_service] = lambda: narration_service
    app.dependency_overrides[narration.get_persona_registry] = lambda: persona_registry
    app.dependency_overrides[qa.get_qa_service] = lambda: qa_service
    app.dependency_overrides[qa.get_persona_registry] = lambda: persona_registry

    app.include_router(health.router)
    app.include_router(poi.router)
    app.include_router(narration.router)
    app.include_router(qa.router)

    return app


try:
    app = create_app(AppConfig())
except Exception:
    app = None  # type: ignore
```

- [ ] **Step 2: 執行全部 backend 測試**

```bash
cd backend && .venv/bin/pytest -v
```

預期：全部通過（145 或更多 passed，0 failed）

- [ ] **Step 3: Commit**

```bash
git add backend/src/tour_guide/main.py
git commit -m "feat(backend): wire QAService and /qa router in app factory"
```

---

## Task 6：Flutter — QaEvent sealed class

**Files:**
- Create: `flutter_app/lib/shared/backend/models/qa_event.dart`
- Modify: `flutter_app/test/unit/models_test.dart`

- [ ] **Step 1: 建立 `qa_event.dart`**

```dart
// flutter_app/lib/shared/backend/models/qa_event.dart
import 'dart:convert';

sealed class QaEvent {}

class TranscriptQaEvent extends QaEvent {
  final String text;
  TranscriptQaEvent({required this.text});
  factory TranscriptQaEvent.fromJson(Map<String, dynamic> j) =>
      TranscriptQaEvent(text: j['text'] as String);
}

class TextQaEvent extends QaEvent {
  final String chunk;
  final int sentenceIdx;
  TextQaEvent({required this.chunk, required this.sentenceIdx});
  factory TextQaEvent.fromJson(Map<String, dynamic> j) => TextQaEvent(
        chunk: j['chunk'] as String,
        sentenceIdx: j['sentence_idx'] as int,
      );
}

class AudioQaEvent extends QaEvent {
  final String chunkB64;
  final int sentenceIdx;
  AudioQaEvent({required this.chunkB64, required this.sentenceIdx});
  factory AudioQaEvent.fromJson(Map<String, dynamic> j) => AudioQaEvent(
        chunkB64: j['chunk_b64'] as String,
        sentenceIdx: j['sentence_idx'] as int,
      );
}

class EndQaEvent extends QaEvent {
  const EndQaEvent();
}

class ErrorQaEvent extends QaEvent {
  final String code;
  final String message;
  ErrorQaEvent({required this.code, required this.message});
  factory ErrorQaEvent.fromJson(Map<String, dynamic> j) => ErrorQaEvent(
        code: j['code'] as String,
        message: j['message'] as String,
      );
}
```

- [ ] **Step 2: 在 `models_test.dart` 末尾新增 QaEvent 測試**

在 `flutter_app/test/unit/models_test.dart` 找到最後一個 `group(` 結束後，新增：

```dart
import 'package:flutter_app/shared/backend/models/qa_event.dart';

// （在 main() 的 group blocks 末尾新增）
group('QaEvent', () {
  test('TranscriptQaEvent.fromJson', () {
    final e = TranscriptQaEvent.fromJson({'text': '這是問題'});
    expect(e.text, '這是問題');
  });

  test('TextQaEvent.fromJson', () {
    final e = TextQaEvent.fromJson({'chunk': '回答', 'sentence_idx': 0});
    expect(e.chunk, '回答');
    expect(e.sentenceIdx, 0);
  });

  test('AudioQaEvent.fromJson', () {
    final e = AudioQaEvent.fromJson({'chunk_b64': 'AAAA', 'sentence_idx': 1});
    expect(e.chunkB64, 'AAAA');
    expect(e.sentenceIdx, 1);
  });

  test('ErrorQaEvent.fromJson', () {
    final e = ErrorQaEvent.fromJson({'code': 'stt_error', 'message': 'timeout'});
    expect(e.code, 'stt_error');
  });
});
```

- [ ] **Step 3: 執行測試**

```bash
cd flutter_app && flutter test test/unit/models_test.dart -v
```

預期：全部通過

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/shared/backend/models/qa_event.dart flutter_app/test/unit/models_test.dart
git commit -m "feat(flutter): add QaEvent sealed class (TranscriptQaEvent, TextQaEvent, AudioQaEvent, EndQaEvent, ErrorQaEvent)"
```

---

## Task 7：Flutter — AudioPlayerService duck/unduck

**Files:**
- Modify: `flutter_app/lib/shared/audio/audio_player_service.dart`
- Create: `flutter_app/test/unit/audio_duck_test.dart`

- [ ] **Step 1: 先寫失敗測試**

```dart
// flutter_app/test/unit/audio_duck_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';

void main() {
  group('FakeAudioPlayerService duck/unduck', () {
    test('isDucked is false by default', () {
      final fake = FakeAudioPlayerService();
      expect(fake.isDucked, isFalse);
    });

    test('duck() sets isDucked to true', () async {
      final fake = FakeAudioPlayerService();
      await fake.duck();
      expect(fake.isDucked, isTrue);
    });

    test('unduck() sets isDucked to false', () async {
      final fake = FakeAudioPlayerService();
      await fake.duck();
      await fake.unduck();
      expect(fake.isDucked, isFalse);
    });
  });
}
```

- [ ] **Step 2: 執行（確認失敗）**

```bash
cd flutter_app && flutter test test/unit/audio_duck_test.dart
```

預期：FAIL（'duck' is not defined）

- [ ] **Step 3: 更新 `audio_player_service.dart`**

完整替換 `audio_player_service.dart`：

```dart
import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';

abstract class AudioPlayerService {
  Future<void> enqueueBytes(Uint8List bytes);
  Future<void> pause();
  Future<void> resume();
  Future<void> skip();
  Future<void> duck();    // 音量降至 50%
  Future<void> unduck();  // 音量恢復 100%
  Stream<bool> get isPlayingStream;
  Future<void> dispose();
}

class RealAudioPlayerService implements AudioPlayerService {
  final AudioPlayer _player = AudioPlayer();
  final ConcatenatingAudioSource _playlist =
      ConcatenatingAudioSource(children: []);
  late final Directory _tempDir;
  int _chunkIndex = 0;
  bool _initialized = false;

  Future<void> _init() async {
    if (_initialized) return;
    _tempDir = await getTemporaryDirectory();
    await _player.setAudioSource(_playlist);
    _initialized = true;
  }

  @override
  Future<void> enqueueBytes(Uint8List bytes) async {
    await _init();
    final file = File('${_tempDir.path}/narration_${_chunkIndex++}.mp3');
    await file.writeAsBytes(bytes);
    await _playlist.add(AudioSource.uri(Uri.file(file.path)));
    if (!_player.playing) await _player.play();
  }

  @override
  Future<void> pause() => _player.pause();

  @override
  Future<void> resume() => _player.play();

  @override
  Future<void> skip() async {
    if (_player.hasNext) {
      await _player.seekToNext();
    } else {
      await _player.stop();
    }
  }

  @override
  Future<void> duck() => _player.setVolume(0.5);

  @override
  Future<void> unduck() => _player.setVolume(1.0);

  @override
  Stream<bool> get isPlayingStream => _player.playingStream;

  @override
  Future<void> dispose() async {
    await _player.stop();
    await _player.dispose();
    for (var i = 0; i < _chunkIndex; i++) {
      final f = File('${_tempDir.path}/narration_$i.mp3');
      if (await f.exists()) await f.delete();
    }
  }
}

class FakeAudioPlayerService implements AudioPlayerService {
  final List<Uint8List> enqueuedChunks = [];
  bool isDucked = false;
  final _controller = StreamController<bool>.broadcast();

  @override
  Future<void> enqueueBytes(Uint8List bytes) async {
    enqueuedChunks.add(bytes);
    _controller.add(true);
  }

  @override
  Future<void> pause() async {
    _controller.add(false);
  }

  @override
  Future<void> resume() async {
    _controller.add(true);
  }

  @override
  Future<void> skip() async {
    _controller.add(false);
  }

  @override
  Future<void> duck() async {
    isDucked = true;
  }

  @override
  Future<void> unduck() async {
    isDucked = false;
  }

  @override
  Stream<bool> get isPlayingStream => _controller.stream;

  @override
  Future<void> dispose() async => _controller.close();
}
```

- [ ] **Step 4: 執行（確認通過）**

```bash
cd flutter_app && flutter test test/unit/audio_duck_test.dart -v
```

預期：3 passed

- [ ] **Step 5: 確認現有測試仍然通過**

```bash
cd flutter_app && flutter test -v
```

預期：53 passed（或更多），0 failed

- [ ] **Step 6: Commit**

```bash
git add flutter_app/lib/shared/audio/audio_player_service.dart flutter_app/test/unit/audio_duck_test.dart
git commit -m "feat(flutter): add duck/unduck to AudioPlayerService for Q&A volume control"
```

---

## Task 8：Flutter — MicRecorderService + record 套件

**Files:**
- Modify: `flutter_app/pubspec.yaml`
- Create: `flutter_app/lib/shared/mic/mic_recorder_service.dart`
- Create: `flutter_app/test/unit/mic_recorder_test.dart`

- [ ] **Step 1: 新增 `record` 套件到 pubspec.yaml**

在 `flutter_app/pubspec.yaml` 的 `dependencies:` 區段，在 `path_provider: ^2.1.3` 後新增：

```yaml
    record: ^5.0.0
```

- [ ] **Step 2: 安裝套件**

```bash
cd flutter_app && flutter pub get
```

預期：成功解析依賴

- [ ] **Step 3: 先寫失敗測試**

```dart
// flutter_app/test/unit/mic_recorder_test.dart
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';

void main() {
  group('FakeMicRecorderService', () {
    test('stopAndGetBytes returns fakeAudio', () async {
      final fake = FakeMicRecorderService(
        fakeAudio: Uint8List.fromList([1, 2, 3, 4]),
      );
      await fake.startRecording();
      final bytes = await fake.stopAndGetBytes();
      expect(bytes, equals(Uint8List.fromList([1, 2, 3, 4])));
    });

    test('cancelRecording does not throw', () async {
      final fake = FakeMicRecorderService();
      await fake.startRecording();
      await fake.cancelRecording();
    });

    test('stopAndGetBytes after cancel returns empty bytes', () async {
      final fake = FakeMicRecorderService();
      await fake.startRecording();
      await fake.cancelRecording();
      final bytes = await fake.stopAndGetBytes();
      expect(bytes, isEmpty);
    });
  });
}
```

- [ ] **Step 4: 執行（確認失敗）**

```bash
cd flutter_app && flutter test test/unit/mic_recorder_test.dart
```

預期：FAIL（ModuleNotFoundError 或找不到 import）

- [ ] **Step 5: 建立 `mic_recorder_service.dart`**

```dart
// flutter_app/lib/shared/mic/mic_recorder_service.dart
import 'dart:io';
import 'dart:typed_data';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

abstract class MicRecorderService {
  Future<void> startRecording();
  Future<Uint8List> stopAndGetBytes();
  Future<void> cancelRecording();
  Future<void> dispose();
}

class RealMicRecorderService implements MicRecorderService {
  final AudioRecorder _recorder = AudioRecorder();
  String? _recordingPath;

  @override
  Future<void> startRecording() async {
    final dir = await getTemporaryDirectory();
    _recordingPath = '${dir.path}/qa_recording_${DateTime.now().millisecondsSinceEpoch}.wav';
    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.wav),
      path: _recordingPath!,
    );
  }

  @override
  Future<Uint8List> stopAndGetBytes() async {
    if (_recordingPath == null) return Uint8List(0);
    final path = await _recorder.stop();
    if (path == null) return Uint8List(0);
    final file = File(path);
    if (!await file.exists()) return Uint8List(0);
    final bytes = await file.readAsBytes();
    await file.delete();
    _recordingPath = null;
    return bytes;
  }

  @override
  Future<void> cancelRecording() async {
    await _recorder.cancel();
    _recordingPath = null;
  }

  @override
  Future<void> dispose() async {
    await _recorder.dispose();
  }
}

class FakeMicRecorderService implements MicRecorderService {
  final Uint8List fakeAudio;
  bool _cancelled = false;

  FakeMicRecorderService({Uint8List? fakeAudio})
      : fakeAudio = fakeAudio ?? Uint8List(0);

  @override
  Future<void> startRecording() async {
    _cancelled = false;
  }

  @override
  Future<Uint8List> stopAndGetBytes() async {
    if (_cancelled) return Uint8List(0);
    return fakeAudio;
  }

  @override
  Future<void> cancelRecording() async {
    _cancelled = true;
  }

  @override
  Future<void> dispose() async {}
}
```

- [ ] **Step 6: 執行（確認通過）**

```bash
cd flutter_app && flutter test test/unit/mic_recorder_test.dart -v
```

預期：3 passed

- [ ] **Step 7: Commit**

```bash
git add flutter_app/pubspec.yaml flutter_app/pubspec.lock flutter_app/lib/shared/mic/mic_recorder_service.dart flutter_app/test/unit/mic_recorder_test.dart
git commit -m "feat(flutter): add MicRecorderService with record package for push-to-talk"
```

---

## Task 9：Flutter — BackendClient.qa()

**Files:**
- Modify: `flutter_app/lib/shared/backend/backend_client.dart`

- [ ] **Step 1: 更新 `backend_client.dart`**

完整替換 `flutter_app/lib/shared/backend/backend_client.dart`：

```dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/backend/sse_parser.dart';

abstract class BackendClient {
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  });

  Stream<NarrationEvent> narrate({
    required String poiId,
    required String persona,
    required String lang,
    required String length,
    bool forceRegenerate = false,
  });

  Stream<QaEvent> qa({
    required Uint8List audioBytes,
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  });
}

class RealBackendClient implements BackendClient {
  final String baseUrl;
  final http.Client _http;

  RealBackendClient({required this.baseUrl}) : _http = http.Client();

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async {
    final uri = Uri.parse('$baseUrl/poi/nearby').replace(
      queryParameters: {
        'lat': lat.toString(),
        'lon': lon.toString(),
        'radius': radius.toString(),
        'lang': lang,
        'persona': persona,
      },
    );
    final response = await _http.get(uri);
    if (response.statusCode != 200) {
      throw Exception('fetchNearby failed: HTTP ${response.statusCode}');
    }
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return (json['pois'] as List)
        .map((e) => POI.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Stream<NarrationEvent> narrate({
    required String poiId,
    required String persona,
    required String lang,
    required String length,
    bool forceRegenerate = false,
  }) async* {
    final request =
        http.Request('POST', Uri.parse('$baseUrl/narration'));
    request.headers['Content-Type'] = 'application/json';
    request.headers['Accept'] = 'text/event-stream';
    request.body = jsonEncode({
      'poi_id': poiId,
      'persona': persona,
      'lang': lang,
      'length': length,
      'force_regenerate': forceRegenerate,
    });
    final response = await _http.send(request);
    if (response.statusCode != 200) {
      throw Exception('narrate failed: HTTP ${response.statusCode}');
    }
    await for (final sseEvent in SseParser.parse(response.stream)) {
      final event = _toNarrationEvent(sseEvent);
      if (event != null) yield event;
    }
  }

  @override
  Stream<QaEvent> qa({
    required Uint8List audioBytes,
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  }) async* {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/qa'));
    request.headers['Accept'] = 'text/event-stream';
    request.files.add(http.MultipartFile.fromBytes(
      'audio',
      audioBytes,
      filename: 'recording.wav',
      contentType: MediaType('audio', 'wav'),
    ));
    request.fields['context'] = jsonEncode({
      'current_poi_id': currentPoiId,
      'persona': persona,
      'lang': lang,
      'narration_so_far': narrationSoFar,
    });

    final response = await _http.send(request);
    if (response.statusCode != 200) {
      throw Exception('qa failed: HTTP ${response.statusCode}');
    }
    await for (final sseEvent in SseParser.parse(response.stream)) {
      final event = _toQaEvent(sseEvent);
      if (event != null) yield event;
    }
  }

  NarrationEvent? _toNarrationEvent(SseEvent sse) => switch (sse.type) {
        'meta' => MetaEvent.fromJson(sse.data),
        'text' => TextEvent.fromJson(sse.data),
        'audio' => AudioEvent.fromJson(sse.data),
        'end' => const EndEvent(),
        'error' => ErrorEvent.fromJson(sse.data),
        _ => ErrorEvent(code: 'unknown', message: 'unknown event: ${sse.type}'),
      };

  QaEvent? _toQaEvent(SseEvent sse) => switch (sse.type) {
        'transcript' => TranscriptQaEvent.fromJson(sse.data),
        'text' => TextQaEvent.fromJson(sse.data),
        'audio' => AudioQaEvent.fromJson(sse.data),
        'end' => const EndQaEvent(),
        'error' => ErrorQaEvent.fromJson(sse.data),
        _ => ErrorQaEvent(code: 'unknown', message: 'unknown event: ${sse.type}'),
      };
}

class FakeBackendClient implements BackendClient {
  final List<POI> nearbyPois;
  final List<NarrationEvent> scriptedEvents;
  final List<QaEvent> scriptedQaEvents;

  const FakeBackendClient({
    this.nearbyPois = const [],
    this.scriptedEvents = const [],
    this.scriptedQaEvents = const [],
  });

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async =>
      nearbyPois;

  @override
  Stream<NarrationEvent> narrate({
    required String poiId,
    required String persona,
    required String lang,
    required String length,
    bool forceRegenerate = false,
  }) async* {
    for (final event in scriptedEvents) {
      yield event;
    }
  }

  @override
  Stream<QaEvent> qa({
    required Uint8List audioBytes,
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  }) async* {
    for (final event in scriptedQaEvents) {
      yield event;
    }
  }
}
```

> 注意：需要 `http_parser` package — `http` 套件已依賴它，可直接 import。

- [ ] **Step 2: 確認 flutter analyze 無 error**

```bash
cd flutter_app && flutter analyze
```

預期：No issues found（或只有 info 等級）

- [ ] **Step 3: 執行全部測試**

```bash
cd flutter_app && flutter test -v
```

預期：全部通過

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/shared/backend/backend_client.dart
git commit -m "feat(flutter): add BackendClient.qa() with multipart/form-data + QaEvent SSE parsing"
```

---

## Task 10：Flutter — Providers 更新

**Files:**
- Modify: `flutter_app/lib/shared/providers.dart`

- [ ] **Step 1: 更新 `providers.dart`**

完整替換 `flutter_app/lib/shared/providers.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';

const _backendUrl = String.fromEnvironment(
  'BACKEND_URL',
  defaultValue: 'http://localhost:8000',
);

final backendClientProvider = Provider<BackendClient>((ref) {
  return RealBackendClient(baseUrl: _backendUrl);
});

final locationServiceProvider = Provider<LocationService>((ref) {
  return RealLocationService();
});

final localDbProvider = Provider<LocalDb>((ref) {
  final db = LocalDb();
  ref.onDispose(db.close);
  return db;
});

final audioPlayerServiceProvider = Provider<AudioPlayerService>((ref) {
  final service = RealAudioPlayerService();
  ref.onDispose(service.dispose);
  return service;
});

// 旁白 AudioPlayer 的別名（語意更清楚）
final narrationAudioPlayerProvider = audioPlayerServiceProvider;

// Q&A 專用 AudioPlayer（獨立實例，不影響旁白音量）
final qaAudioPlayerProvider = Provider<AudioPlayerService>((ref) {
  final service = RealAudioPlayerService();
  ref.onDispose(service.dispose);
  return service;
});

final micRecorderProvider = Provider<MicRecorderService>((ref) {
  final service = RealMicRecorderService();
  ref.onDispose(service.dispose);
  return service;
});
```

- [ ] **Step 2: 執行全部測試**

```bash
cd flutter_app && flutter test -v
```

預期：全部通過

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/shared/providers.dart
git commit -m "feat(flutter): add qaAudioPlayerProvider and micRecorderProvider"
```

---

## Task 11：Flutter — QaNotifier（TDD）

**Files:**
- Create: `flutter_app/lib/features/qa/providers/qa_provider.dart`
- Create: `flutter_app/test/unit/qa_provider_test.dart`

- [ ] **Step 1: 先寫失敗測試**

```dart
// flutter_app/test/unit/qa_provider_test.dart
import 'dart:typed_data';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/qa/providers/qa_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';
import 'package:flutter_app/shared/providers.dart';

final _scriptedQaEvents = [
  TranscriptQaEvent(text: '這裡有多少文物？'),
  TextQaEvent(chunk: '故宮有約七十萬件文物。', sentenceIdx: 0),
  AudioQaEvent(chunkB64: 'AAAA', sentenceIdx: 0),
  const EndQaEvent(),
];

ProviderContainer _makeContainer({
  List<QaEvent> qaEvents = const [],
}) {
  final fakeNarrationAudio = FakeAudioPlayerService();
  final fakeQaAudio = FakeAudioPlayerService();
  final fakeMic = FakeMicRecorderService(
    fakeAudio: Uint8List.fromList([1, 2, 3]),
  );
  final fakeClient = FakeBackendClient(scriptedQaEvents: qaEvents);

  return ProviderContainer(
    overrides: [
      backendClientProvider.overrideWithValue(fakeClient),
      narrationAudioPlayerProvider.overrideWithValue(fakeNarrationAudio),
      qaAudioPlayerProvider.overrideWithValue(fakeQaAudio),
      micRecorderProvider.overrideWithValue(fakeMic),
    ],
  );
}

void main() {
  group('QaNotifier', () {
    test('initial status is idle', () {
      final container = _makeContainer();
      addTearDown(container.dispose);
      expect(container.read(qaProvider).status, QaStatus.idle);
    });

    test('startRecording transitions to recording', () async {
      final container = _makeContainer();
      addTearDown(container.dispose);
      await container.read(qaProvider.notifier).startRecording();
      expect(container.read(qaProvider).status, QaStatus.recording);
    });

    test('startRecording ducks narration audio', () async {
      final fakeNarrationAudio = FakeAudioPlayerService();
      final container = ProviderContainer(
        overrides: [
          backendClientProvider.overrideWithValue(const FakeBackendClient()),
          narrationAudioPlayerProvider.overrideWithValue(fakeNarrationAudio),
          qaAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
          micRecorderProvider.overrideWithValue(FakeMicRecorderService()),
        ],
      );
      addTearDown(container.dispose);
      await container.read(qaProvider.notifier).startRecording();
      expect(fakeNarrationAudio.isDucked, isTrue);
    });

    test('stopAndSend transitions through processing → answering → idle', () async {
      final container = _makeContainer(qaEvents: _scriptedQaEvents);
      addTearDown(container.dispose);

      final statuses = <QaStatus>[];
      container.listen(
        qaProvider.select((s) => s.status),
        (_, next) => statuses.add(next),
      );

      await container.read(qaProvider.notifier).startRecording();
      await container.read(qaProvider.notifier).stopAndSend(
        persona: 'history_uncle',
        lang: 'zh-TW',
        currentPoiId: 'osm:1',
        narrationSoFar: '故宮是台灣最重要的博物館。',
      );
      await Future<void>.delayed(Duration.zero);

      expect(statuses, contains(QaStatus.processing));
    });

    test('stopAndSend sets transcript from TranscriptQaEvent', () async {
      final container = _makeContainer(qaEvents: _scriptedQaEvents);
      addTearDown(container.dispose);

      await container.read(qaProvider.notifier).startRecording();
      await container.read(qaProvider.notifier).stopAndSend(
        persona: 'history_uncle',
        lang: 'zh-TW',
      );
      await Future<void>.delayed(Duration.zero);

      expect(container.read(qaProvider).transcript, contains('這裡有多少文物'));
    });

    test('cancelRecording resets to idle and unduckes audio', () async {
      final fakeNarrationAudio = FakeAudioPlayerService();
      final container = ProviderContainer(
        overrides: [
          backendClientProvider.overrideWithValue(const FakeBackendClient()),
          narrationAudioPlayerProvider.overrideWithValue(fakeNarrationAudio),
          qaAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
          micRecorderProvider.overrideWithValue(FakeMicRecorderService()),
        ],
      );
      addTearDown(container.dispose);

      await container.read(qaProvider.notifier).startRecording();
      await container.read(qaProvider.notifier).cancelRecording();
      expect(container.read(qaProvider).status, QaStatus.idle);
      expect(fakeNarrationAudio.isDucked, isFalse);
    });
  });
}
```

- [ ] **Step 2: 執行（確認失敗）**

```bash
cd flutter_app && flutter test test/unit/qa_provider_test.dart
```

預期：FAIL（找不到 qa_provider.dart）

- [ ] **Step 3: 實作 QaNotifier**

先建立目錄：
```bash
mkdir -p flutter_app/lib/features/qa/providers
```

```dart
// flutter_app/lib/features/qa/providers/qa_provider.dart
import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';
import 'package:flutter_app/shared/providers.dart';

enum QaStatus { idle, recording, processing, answering, error }

class QaState {
  final QaStatus status;
  final String transcript;
  final String responseText;
  final String? errorMessage;

  const QaState({
    required this.status,
    this.transcript = '',
    this.responseText = '',
    this.errorMessage,
  });

  QaState copyWith({
    QaStatus? status,
    String? transcript,
    String? responseText,
    String? errorMessage,
  }) =>
      QaState(
        status: status ?? this.status,
        transcript: transcript ?? this.transcript,
        responseText: responseText ?? this.responseText,
        errorMessage: errorMessage ?? this.errorMessage,
      );
}

class QaNotifier extends StateNotifier<QaState> {
  QaNotifier(
    this._client,
    this._narrationAudio,
    this._qaAudio,
    this._mic,
  ) : super(const QaState(status: QaStatus.idle));

  final BackendClient _client;
  final AudioPlayerService _narrationAudio;
  final AudioPlayerService _qaAudio;
  final MicRecorderService _mic;
  StreamSubscription<QaEvent>? _sub;
  DateTime? _recordingStartedAt;

  Future<void> startRecording() async {
    await _sub?.cancel();
    _sub = null;
    await _narrationAudio.duck();
    await _mic.startRecording();
    _recordingStartedAt = DateTime.now();
    state = state.copyWith(
      status: QaStatus.recording,
      transcript: '',
      responseText: '',
      errorMessage: null,
    );
  }

  Future<void> stopAndSend({
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  }) async {
    final started = _recordingStartedAt;
    _recordingStartedAt = null;

    // guard: < 500ms → silent cancel
    if (started != null &&
        DateTime.now().difference(started).inMilliseconds < 500) {
      await cancelRecording();
      return;
    }

    final audioBytes = await _mic.stopAndGetBytes();
    state = state.copyWith(status: QaStatus.processing);

    _sub = _client
        .qa(
          audioBytes: audioBytes,
          persona: persona,
          lang: lang,
          currentPoiId: currentPoiId,
          narrationSoFar: narrationSoFar,
        )
        .listen(
          _handleEvent,
          onError: (Object e) async {
            await _narrationAudio.unduck();
            state = state.copyWith(
              status: QaStatus.error,
              errorMessage: e.toString(),
            );
          },
        );
  }

  void _handleEvent(QaEvent event) {
    switch (event) {
      case TranscriptQaEvent(:final text):
        state = state.copyWith(
          status: QaStatus.answering,
          transcript: '你說：$text',
        );
      case TextQaEvent(:final chunk):
        state = state.copyWith(responseText: state.responseText + chunk);
      case AudioQaEvent(:final chunkB64):
        _qaAudio.enqueueBytes(base64.decode(chunkB64));
      case EndQaEvent():
        _narrationAudio.unduck();
        state = state.copyWith(status: QaStatus.idle);
      case ErrorQaEvent(:final message):
        _narrationAudio.unduck();
        state = state.copyWith(
          status: QaStatus.error,
          errorMessage: message,
        );
    }
  }

  Future<void> cancelRecording() async {
    await _sub?.cancel();
    _sub = null;
    await _mic.cancelRecording();
    await _narrationAudio.unduck();
    state = const QaState(status: QaStatus.idle);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final qaProvider = StateNotifierProvider<QaNotifier, QaState>((ref) {
  return QaNotifier(
    ref.watch(backendClientProvider),
    ref.watch(narrationAudioPlayerProvider),
    ref.watch(qaAudioPlayerProvider),
    ref.watch(micRecorderProvider),
  );
});
```

- [ ] **Step 4: 執行（確認通過）**

```bash
cd flutter_app && flutter test test/unit/qa_provider_test.dart -v
```

預期：6 passed

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/qa/providers/qa_provider.dart flutter_app/test/unit/qa_provider_test.dart
git commit -m "feat(flutter): add QaNotifier with idle/recording/processing/answering state machine (TDD)"
```

---

## Task 12：Flutter — PushToTalkButton Widget

**Files:**
- Create: `flutter_app/lib/features/qa/widgets/push_to_talk_button.dart`
- Create: `flutter_app/test/widget/push_to_talk_button_test.dart`

- [ ] **Step 1: 先寫失敗測試**

```dart
// flutter_app/test/widget/push_to_talk_button_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/qa/providers/qa_provider.dart';
import 'package:flutter_app/features/qa/widgets/push_to_talk_button.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';
import 'package:flutter_app/shared/providers.dart';

// Fake SessionNotifier — mirrors pattern in narration_sheet_test.dart
class _FakeSessionNotifier extends StateNotifier<SessionState>
    implements SessionNotifier {
  _FakeSessionNotifier(SessionStatus status)
      : super(SessionState(
          status: status,
          persona: 'history_uncle',
          lang: 'zh-TW',
        ));

  @override void setPersona(String persona) {}
  @override void setLang(String lang) {}
  @override Future<void> start() async {}
  @override Future<void> stop() async {}
}

Widget _wrap(Widget child, {SessionStatus sessionStatus = SessionStatus.active}) {
  return ProviderScope(
    overrides: [
      backendClientProvider.overrideWithValue(const FakeBackendClient()),
      narrationAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
      qaAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
      micRecorderProvider.overrideWithValue(FakeMicRecorderService()),
      sessionProvider.overrideWith(
        (ref) => _FakeSessionNotifier(sessionStatus),
      ),
    ],
    child: MaterialApp(home: Scaffold(body: child)),
  );
}

void main() {
  group('PushToTalkButton', () {
    testWidgets('shows mic icon when idle and session active', (tester) async {
      await tester.pumpWidget(_wrap(const PushToTalkButton()));
      expect(find.byIcon(Icons.mic), findsOneWidget);
    });

    testWidgets('hidden when session is not active', (tester) async {
      await tester.pumpWidget(_wrap(
        const PushToTalkButton(),
        sessionStatus: SessionStatus.idle,
      ));
      expect(find.byType(SizedBox), findsWidgets);
      expect(find.byIcon(Icons.mic), findsNothing);
    });
  });
}
```

- [ ] **Step 2: 執行（確認失敗）**

```bash
cd flutter_app && flutter test test/widget/push_to_talk_button_test.dart
```

預期：FAIL（找不到 push_to_talk_button.dart）

- [ ] **Step 3: 建立目錄並實作 widget**

```bash
mkdir -p flutter_app/lib/features/qa/widgets
```

```dart
// flutter_app/lib/features/qa/widgets/push_to_talk_button.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/qa/providers/qa_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';

class PushToTalkButton extends ConsumerWidget {
  const PushToTalkButton({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    if (session.status != SessionStatus.active) return const SizedBox.shrink();

    final qa = ref.watch(qaProvider);

    return GestureDetector(
      onLongPressStart: (_) {
        ref.read(qaProvider.notifier).startRecording();
      },
      onLongPressEnd: (_) {
        final narration = ref.read(narrationProvider);
        final sessionState = ref.read(sessionProvider);
        ref.read(qaProvider.notifier).stopAndSend(
          persona: sessionState.persona,
          lang: sessionState.lang,
          currentPoiId: narration.currentPoi?.id,
          narrationSoFar: narration.subtitle,
        );
      },
      onLongPressCancel: () {
        ref.read(qaProvider.notifier).cancelRecording();
      },
      child: _buildIcon(qa.status),
    );
  }

  Widget _buildIcon(QaStatus status) {
    return switch (status) {
      QaStatus.idle => _CircleButton(
          icon: Icons.mic,
          color: Colors.white,
          backgroundColor: const Color(0xFF4A9EFF),
        ),
      QaStatus.recording => _PulsingButton(),
      QaStatus.processing => const SizedBox(
          width: 56,
          height: 56,
          child: CircularProgressIndicator(
            color: Color(0xFF4A9EFF),
            strokeWidth: 3,
          ),
        ),
      QaStatus.answering => _CircleButton(
          icon: Icons.volume_up,
          color: Colors.white,
          backgroundColor: const Color(0xFF4A9EFF),
        ),
      QaStatus.error => _CircleButton(
          icon: Icons.warning_amber,
          color: Colors.white,
          backgroundColor: Colors.orange,
        ),
    };
  }
}

class _CircleButton extends StatelessWidget {
  const _CircleButton({
    required this.icon,
    required this.color,
    required this.backgroundColor,
  });

  final IconData icon;
  final Color color;
  final Color backgroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: backgroundColor,
        boxShadow: const [
          BoxShadow(
            color: Colors.black26,
            blurRadius: 8,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Icon(icon, color: color, size: 28),
    );
  }
}

class _PulsingButton extends StatefulWidget {
  @override
  State<_PulsingButton> createState() => _PulsingButtonState();
}

class _PulsingButtonState extends State<_PulsingButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 600),
  )..repeat(reverse: true);
  late final Animation<double> _scale =
      Tween<double>(begin: 0.9, end: 1.1).animate(_controller);

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: _scale,
      child: Container(
        width: 56,
        height: 56,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: Colors.red,
        ),
        child: const Icon(Icons.mic, color: Colors.white, size: 28),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}
```

- [ ] **Step 4: 執行（確認通過）**

```bash
cd flutter_app && flutter test test/widget/push_to_talk_button_test.dart -v
```

預期：2 passed

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/qa/widgets/push_to_talk_button.dart flutter_app/test/widget/push_to_talk_button_test.dart
git commit -m "feat(flutter): add PushToTalkButton widget with idle/recording/processing/answering states"
```

---

## Task 13：Flutter — MapScreen 整合 PushToTalkButton

**Files:**
- Modify: `flutter_app/lib/features/map/screens/map_screen.dart`

- [ ] **Step 1: 更新 MapScreen**

在 `flutter_app/lib/features/map/screens/map_screen.dart` 中：

1. 新增 import：
```dart
import 'package:flutter_app/features/qa/widgets/push_to_talk_button.dart';
```

2. 在 `body:` 的 Stack children 中，`NarrationSheet` 之後新增 PushToTalkButton：

```dart
body: Stack(
  children: [
    GoogleMap(
      initialCameraPosition: CameraPosition(
        target: initialTarget,
        zoom: 16,
      ),
      myLocationEnabled: true,
      myLocationButtonEnabled: true,
      markers: markers,
      onMapCreated: (c) => _mapController = c,
    ),
    const Align(
      alignment: Alignment.bottomCenter,
      child: NarrationSheet(),
    ),
    const Positioned(
      bottom: 100,   // NarrationSheet minibar 高度上方
      left: 0,
      right: 0,
      child: Center(child: PushToTalkButton()),
    ),
  ],
),
```

- [ ] **Step 2: flutter analyze**

```bash
cd flutter_app && flutter analyze
```

預期：No issues found（或只有 info）

- [ ] **Step 3: 執行全部測試**

```bash
cd flutter_app && flutter test -v
```

預期：全部通過

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/map/screens/map_screen.dart
git commit -m "feat(flutter): integrate PushToTalkButton into MapScreen"
```

---

## Task 14：Flutter — NarrationSheet 顯示 Q&A 字幕

**Files:**
- Modify: `flutter_app/lib/features/narration/widgets/narration_sheet.dart`
- Modify: `flutter_app/test/widget/narration_sheet_test.dart`

- [ ] **Step 1: 更新 NarrationSheet**

在 `flutter_app/lib/features/narration/widgets/narration_sheet.dart` 中：

1. 新增 import：
```dart
import 'package:flutter_app/features/qa/providers/qa_provider.dart';
```

2. 在 `build()` 方法中，`ListView` children 的 `state.subtitle` Text widget 前，新增 Q&A 字幕區塊：

在 `const SizedBox(height: 8),` 與顯示 subtitle 的 `Text(state.subtitle, ...)` 之間插入：

```dart
// Q&A 字幕區塊（僅在 Q&A 進行中時顯示）
Consumer(
  builder: (context, ref, _) {
    final qa = ref.watch(qaProvider);
    if (qa.status == QaStatus.idle && qa.transcript.isEmpty) {
      return const SizedBox.shrink();
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: const Color(0xFF0A2240),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (qa.transcript.isNotEmpty)
            Text(
              qa.transcript,
              style: const TextStyle(
                color: Color(0xFF4A9EFF),
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          if (qa.responseText.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                qa.responseText,
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 13,
                  height: 1.5,
                ),
              ),
            ),
        ],
      ),
    );
  },
),
```

- [ ] **Step 2: 執行全部測試**

```bash
cd flutter_app && flutter test -v
```

預期：全部通過

- [ ] **Step 3: flutter analyze**

```bash
cd flutter_app && flutter analyze
```

預期：No issues found（或只有 info）

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/narration/widgets/narration_sheet.dart
git commit -m "feat(flutter): show Q&A transcript and response text in NarrationSheet"
```

---

## Task 15：最終驗收

- [ ] **Step 1: 執行全部 backend 測試**

```bash
cd backend && .venv/bin/pytest -v
```

預期：全部通過，0 failed

- [ ] **Step 2: 執行全部 Flutter 測試**

```bash
cd flutter_app && flutter test -v
```

預期：全部通過，0 failed

- [ ] **Step 3: flutter analyze**

```bash
cd flutter_app && flutter analyze
```

預期：No issues found（或只有 info）

- [ ] **Step 4: 最終統整 Commit（若有未 commit 的內容）**

```bash
git add -p  # 逐一確認
git commit -m "feat: Plan D push-to-talk Q&A complete — STT→LLM→TTS pipeline, duck/unduck, PushToTalkButton"
```

---

## 驗收標準

| 項目 | 標準 |
|---|---|
| Backend tests | 全部通過，包含 /qa integration test |
| Flutter tests | 全部通過（QaNotifier 6 tests + PushToTalkButton 2 tests + duck/unduck 3 tests） |
| flutter analyze | No error/warning |
| 手動 smoke | 後端啟動後，用 curl multipart 測試 /qa endpoint 可收到 SSE 事件 |

```bash
# 手動驗收 /qa endpoint
cd backend && GEMINI_API_KEY=fake .venv/bin/uvicorn tour_guide.main:app --reload &

curl -X POST http://localhost:8000/qa \
  -F "audio=@/dev/null;type=audio/wav" \
  -F 'context={"current_poi_id":"osm:1","persona":"history_uncle","lang":"zh-TW","narration_so_far":""}' \
  -H "Accept: text/event-stream"
```

預期：收到 `event: transcript`、`event: text`、`event: audio`、`event: end`（或 error event，因為用 fake key）
