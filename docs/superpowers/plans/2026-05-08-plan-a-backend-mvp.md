# Plan A: Backend MVP — Single Persona Narration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python/FastAPI backend that, given a coordinate or POI ID, streams audio narration in the voice of a single persona (`history_uncle`, zh-TW), using OSM + Wikipedia for context and Gemini for LLM + TTS.

**Architecture:** Layered backend with strict provider abstraction. Pure-function modules (`SentenceSplitter`, `ConfidenceClassifier`, `PromptBuilder`) are TDD-built first. External services (Overpass, Wikipedia, Gemini) hide behind interfaces with fake test doubles, enabling fully-offline integration tests. SSE streams `meta`/`text`/`audio`/`end`/`error` events to the client. No auth, no cache invalidation policy beyond LRU/TTL — both deferred concerns for later plans.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, sse-starlette, pydantic / pydantic-settings, httpx, litellm, google-genai, PyYAML, pytest, pytest-asyncio, respx, freezegun, ruff.

**Spec reference:** `docs/superpowers/specs/2026-05-08-ai-tour-guide-design.md` — sections 4.2 (backend modules), 6 (API), 7.2 (backend cache), 8 (persona / multi-language), 10.2 (testing).

**Out of scope for Plan A** (deferred to later plans):
- `/qa` endpoint and STT (Plan D)
- Other 3 personas + multi-language (Plan C)
- Foodie persona + Google Places (Plan E)
- Cloud Run deployment + `X-API-Key` (Plan F)
- Persona-coloured system messages + confidence labels client-side (Plan C)

---

## File Structure

```text
backend/
├── pyproject.toml                       # PEP 621 project + deps
├── ruff.toml                            # linter config
├── pytest.ini                           # test config + marker registry
├── README.md                            # setup, run, curl recipes
├── .env.example                         # GEMINI_API_KEY etc.
├── prompts/
│   └── personas/
│       └── history_uncle.yaml           # persona definition (zh-TW only in Plan A)
├── src/
│   └── tour_guide/
│       ├── __init__.py
│       ├── main.py                      # FastAPI app factory + DI wiring
│       ├── config.py                    # pydantic-settings AppConfig
│       ├── api/
│       │   ├── __init__.py
│       │   ├── health.py                # GET /health
│       │   ├── poi.py                   # GET /poi/nearby
│       │   ├── narration.py             # POST /narration (SSE)
│       │   └── sse.py                   # SSE event encoding helpers
│       ├── services/
│       │   ├── __init__.py
│       │   ├── poi_service.py           # combines Overpass + Wikipedia + cache
│       │   ├── narration_service.py     # orchestrates prompt → LLM → splitter → TTS
│       │   └── confidence.py            # ConfidenceClassifier (pure)
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── llm.py                   # LlmProvider interface + LiteLLM impl
│       │   ├── tts.py                   # TtsProvider interface + Gemini impl
│       │   └── fakes.py                 # Fake providers for tests
│       ├── clients/
│       │   ├── __init__.py
│       │   ├── overpass.py              # OverpassClient
│       │   └── wikipedia.py             # WikipediaClient
│       ├── prompts/
│       │   ├── __init__.py
│       │   ├── loader.py                # YAML → PersonaConfig
│       │   └── builder.py               # PromptBuilder (pure)
│       ├── pipeline/
│       │   ├── __init__.py
│       │   └── sentence_splitter.py     # streaming-safe sentence splitter (pure)
│       ├── cache/
│       │   ├── __init__.py
│       │   ├── poi_cache.py             # filesystem POI cache
│       │   └── narration_cache.py       # filesystem narration cache
│       └── models/
│           ├── __init__.py
│           ├── poi.py                   # POI, POIContext, Wiki dataclasses
│           └── persona.py               # PersonaConfig dataclass
└── tests/
    ├── conftest.py                      # shared fixtures
    ├── unit/
    │   ├── test_sentence_splitter.py
    │   ├── test_confidence.py
    │   ├── test_prompt_builder.py
    │   ├── test_persona_loader.py
    │   ├── test_poi_filter.py
    │   ├── test_poi_cache.py
    │   └── test_narration_cache.py
    ├── integration/
    │   ├── test_health_api.py
    │   ├── test_poi_api.py
    │   ├── test_narration_api.py
    │   └── test_overpass_client.py     # uses respx
    └── smoke/
        └── test_real_providers.py       # @pytest.mark.real_provider
```

All work in Plan A is inside `backend/`. The Flutter app does not exist yet.

---

## Tasks

### Task 1: Initialize backend project skeleton

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/ruff.toml`
- Create: `backend/pytest.ini`
- Create: `backend/.env.example`
- Create: `backend/README.md`
- Create: `backend/src/tour_guide/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "tour-guide-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.29.0",
    "sse-starlette>=2.1.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "httpx>=0.27.0",
    "litellm>=1.40.0",
    "google-genai>=0.3.0",
    "PyYAML>=6.0",
    "aiofiles>=23.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.4.0",
    "respx>=0.21",
    "freezegun>=1.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/tour_guide"]
```

- [ ] **Step 2: Create `backend/ruff.toml`**

```toml
target-version = "py312"
line-length = 100

[lint]
select = ["E", "F", "I", "B", "UP", "ASYNC", "S", "RUF"]
ignore = ["S101"]   # allow asserts in tests

[lint.per-file-ignores]
"tests/**" = ["S"]
```

- [ ] **Step 3: Create `backend/pytest.ini`**

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
markers =
    real_provider: hits a real external service (Gemini/Overpass/Wikipedia); skipped by default

addopts = -ra --strict-markers
```

- [ ] **Step 4: Create `backend/.env.example`**

```bash
# Gemini API
GEMINI_API_KEY=your-key-here

# Backend service
HOST=0.0.0.0
PORT=8000

# Cache directories (defaults to /tmp/tour_guide_cache, /tmp/tour_guide_narration_cache)
POI_CACHE_DIR=
NARRATION_CACHE_DIR=
```

- [ ] **Step 5: Create `backend/README.md`**

```markdown
# Tour Guide Backend

## Setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # then edit with your GEMINI_API_KEY
```

## Run

```bash
uvicorn tour_guide.main:app --reload
```

## Test

```bash
pytest                            # unit + integration (offline)
pytest -m real_provider           # smoke test against real Gemini (costs $)
```
```

- [ ] **Step 6: Create empty package files**

```bash
mkdir -p backend/src/tour_guide backend/tests/unit backend/tests/integration backend/tests/smoke
touch backend/src/tour_guide/__init__.py
touch backend/tests/__init__.py backend/tests/unit/__init__.py backend/tests/integration/__init__.py backend/tests/smoke/__init__.py
```

- [ ] **Step 7: Create `backend/tests/conftest.py` (empty placeholder)**

```python
"""Shared pytest fixtures live here."""
```

- [ ] **Step 8: Install + verify**

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest --version
```
Expected: pytest version printed, no errors.

- [ ] **Step 9: Commit**

```bash
git add backend/
git commit -m "feat(backend): initialize Python project skeleton

- pyproject.toml with FastAPI, LiteLLM, google-genai, pytest, ruff
- ruff + pytest config with real_provider marker
- src/ layout, empty packages
- README and .env.example"
```

---

### Task 2: First passing test (smoke that pytest runs)

**Files:**
- Create: `backend/tests/unit/test_smoke.py`

- [ ] **Step 1: Write the failing test**

```python
def test_python_works():
    assert 1 + 1 == 2
```

- [ ] **Step 2: Run**

```bash
cd backend && pytest tests/unit/test_smoke.py -v
```
Expected: `1 passed`.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_smoke.py
git commit -m "test(backend): smoke test confirming pytest runs"
```

---

### Task 3: SentenceSplitter — basic Chinese + English splitting

**Files:**
- Create: `backend/tests/unit/test_sentence_splitter.py`
- Create: `backend/src/tour_guide/pipeline/__init__.py`
- Create: `backend/src/tour_guide/pipeline/sentence_splitter.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from tour_guide.pipeline.sentence_splitter import split_complete_text

class TestSplitCompleteText:
    def test_splits_on_chinese_period(self):
        result = split_complete_text("故宮博物院位於台北。它建於 1925 年。")
        assert result == ["故宮博物院位於台北。", "它建於 1925 年。"]

    def test_splits_on_english_period(self):
        result = split_complete_text("Hello world. How are you?")
        assert result == ["Hello world.", "How are you?"]

    def test_handles_chinese_exclamation(self):
        result = split_complete_text("真的很美！下一個是哪裡？")
        assert result == ["真的很美！", "下一個是哪裡？"]

    def test_strips_leading_whitespace_between_sentences(self):
        result = split_complete_text("第一句。  第二句。")
        assert result == ["第一句。", "第二句。"]

    def test_keeps_trailing_text_without_terminator(self):
        result = split_complete_text("第一句。 還沒講完")
        assert result == ["第一句。", "還沒講完"]

    def test_empty_string_returns_empty_list(self):
        assert split_complete_text("") == []

    def test_only_whitespace_returns_empty_list(self):
        assert split_complete_text("   \n  ") == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_sentence_splitter.py -v
```
Expected: ImportError on `tour_guide.pipeline.sentence_splitter`.

- [ ] **Step 3: Implement `backend/src/tour_guide/pipeline/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Implement `backend/src/tour_guide/pipeline/sentence_splitter.py`**

```python
"""Sentence splitter for streaming LLM output (zh-TW + en)."""
import re

_TERMINATORS = "。！？.!?"
_SPLIT_RE = re.compile(rf"([^{re.escape(_TERMINATORS)}]*[{re.escape(_TERMINATORS)}])")


def split_complete_text(text: str) -> list[str]:
    """Split a complete (non-streaming) text into sentences.

    Sentences end on Chinese (。！？) or ASCII (.!?) terminators.
    Trailing text without terminator is returned as the last sentence.
    Empty / whitespace-only input returns [].
    """
    text = text.strip()
    if not text:
        return []

    parts = _SPLIT_RE.findall(text)
    consumed_len = sum(len(p) for p in parts)
    sentences = [p.strip() for p in parts if p.strip()]

    tail = text[consumed_len:].strip()
    if tail:
        sentences.append(tail)
    return sentences
```

- [ ] **Step 5: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_sentence_splitter.py -v
```
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/pipeline/ backend/tests/unit/test_sentence_splitter.py
git commit -m "feat(pipeline): SentenceSplitter — basic Chinese + English splitting"
```

---

### Task 4: SentenceSplitter — streaming-safe `StreamingSentenceBuffer`

**Files:**
- Modify: `backend/src/tour_guide/pipeline/sentence_splitter.py`
- Modify: `backend/tests/unit/test_sentence_splitter.py`

- [ ] **Step 1: Write the failing test (append to existing file)**

```python
from tour_guide.pipeline.sentence_splitter import StreamingSentenceBuffer


class TestStreamingSentenceBuffer:
    def test_emits_sentence_when_terminator_arrives(self):
        buf = StreamingSentenceBuffer()
        assert buf.feed("故宮博物院位於") == []
        assert buf.feed("台北。它建於") == ["故宮博物院位於台北。"]
        assert buf.feed("1925 年。") == ["它建於1925 年。"]
        assert buf.flush() == []

    def test_holds_partial_sentence_until_flush(self):
        buf = StreamingSentenceBuffer()
        buf.feed("沒有終止符號的尾巴")
        assert buf.flush() == ["沒有終止符號的尾巴"]

    def test_multiple_sentences_in_one_chunk(self):
        buf = StreamingSentenceBuffer()
        result = buf.feed("第一句。第二句。第三句。")
        assert result == ["第一句。", "第二句。", "第三句。"]
        assert buf.flush() == []

    def test_english_streaming(self):
        buf = StreamingSentenceBuffer()
        assert buf.feed("Hello") == []
        assert buf.feed(" world.") == ["Hello world."]

    def test_flush_is_idempotent_when_empty(self):
        buf = StreamingSentenceBuffer()
        assert buf.flush() == []
        assert buf.flush() == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_sentence_splitter.py::TestStreamingSentenceBuffer -v
```
Expected: ImportError on `StreamingSentenceBuffer`.

- [ ] **Step 3: Append to `backend/src/tour_guide/pipeline/sentence_splitter.py`**

```python
class StreamingSentenceBuffer:
    """Accumulates streaming text chunks and emits whole sentences as they complete."""

    def __init__(self) -> None:
        self._buf: str = ""

    def feed(self, chunk: str) -> list[str]:
        """Add a chunk and return any newly completed sentences."""
        self._buf += chunk
        out: list[str] = []
        # Find every terminator in the buffer; everything up to and including each
        # terminator is a complete sentence. The remainder stays buffered.
        last_cut = 0
        for i, ch in enumerate(self._buf):
            if ch in _TERMINATORS:
                sentence = self._buf[last_cut : i + 1].strip()
                if sentence:
                    out.append(sentence)
                last_cut = i + 1
        self._buf = self._buf[last_cut:]
        return out

    def flush(self) -> list[str]:
        """Return any remaining buffered text as a final sentence (no terminator)."""
        tail = self._buf.strip()
        self._buf = ""
        return [tail] if tail else []
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_sentence_splitter.py -v
```
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/pipeline/sentence_splitter.py backend/tests/unit/test_sentence_splitter.py
git commit -m "feat(pipeline): StreamingSentenceBuffer for incremental LLM output"
```

---

### Task 5: POI / PersonaConfig data models

**Files:**
- Create: `backend/src/tour_guide/models/__init__.py`
- Create: `backend/src/tour_guide/models/poi.py`
- Create: `backend/src/tour_guide/models/persona.py`

- [ ] **Step 1: Create `backend/src/tour_guide/models/__init__.py`**

```python
```
(empty)

- [ ] **Step 2: Create `backend/src/tour_guide/models/poi.py`**

```python
"""Data models for POIs and their context."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


class WikiArticle(BaseModel):
    title: str
    extract: str
    url: str


class POI(BaseModel):
    """A point of interest discoverable via the OSM/Wikipedia pipeline."""

    id: str = Field(..., description="e.g. 'osm:way:12345'")
    name: str
    name_localized: str
    lat: float
    lon: float
    tags: dict[str, str] = Field(default_factory=dict)
    wiki: WikiArticle | None = None
    distance_m: int | None = None
    confidence: Confidence = "low"


class POIContext(BaseModel):
    """Full context for a POI, used by PromptBuilder to compose the LLM prompt."""

    poi: POI
    background_text: str = Field(
        ..., description="Concatenated narrative text the LLM should use as source material."
    )
    confidence: Confidence
```

- [ ] **Step 3: Create `backend/src/tour_guide/models/persona.py`**

```python
"""Data model for a persona configuration loaded from YAML."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LangCode = Literal["zh-TW", "en"]
PoiSource = Literal["osm_wikipedia", "google_places"]
NarrationLength = Literal["short", "medium", "long"]


class VoiceStyle(BaseModel):
    speaking_rate: float = 1.0
    emotion: str | None = None


class StyleProfile(BaseModel):
    embellishment: float = Field(0.3, ge=0.0, le=1.0)
    preferred_topics: list[str] = Field(default_factory=list)
    speech_quirks: list[str] = Field(default_factory=list)


class PersonaConfig(BaseModel):
    id: str
    display_name: dict[LangCode, str]
    description: dict[LangCode, str]
    voice: dict[LangCode, str]
    voice_style: VoiceStyle = VoiceStyle()
    style_profile: StyleProfile = StyleProfile()
    poi_source: PoiSource = "osm_wikipedia"
    default_trigger_radius_m: int = 100

    system_prompt: dict[LangCode, str]
    narration_template: dict[LangCode, str]
    qa_template: dict[LangCode, str] = Field(default_factory=dict)
    system_messages: dict[LangCode, dict[str, list[str]]] = Field(default_factory=dict)
    confidence_labels: dict[LangCode, dict[str, list[str] | None]] = Field(default_factory=dict)
```

- [ ] **Step 4: Verify it imports cleanly**

```bash
cd backend && python -c "from tour_guide.models.poi import POI, POIContext, WikiArticle; from tour_guide.models.persona import PersonaConfig; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/models/
git commit -m "feat(models): add POI, POIContext, PersonaConfig pydantic models"
```

---

### Task 6: PersonaLoader — load YAML to PersonaConfig

**Files:**
- Create: `backend/src/tour_guide/prompts/__init__.py`
- Create: `backend/src/tour_guide/prompts/loader.py`
- Create: `backend/tests/unit/test_persona_loader.py`
- Create: `backend/prompts/personas/history_uncle.yaml`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from tour_guide.prompts.loader import load_persona, load_all_personas
from tour_guide.models.persona import PersonaConfig


def test_load_persona_returns_config(tmp_path: Path):
    yaml_text = """
id: history_uncle
display_name:
  zh-TW: 歷史大叔
  en: The History Uncle
description:
  zh-TW: 沉穩深度
  en: Calm and deep
voice:
  zh-TW: Charon
  en: Charon
poi_source: osm_wikipedia
default_trigger_radius_m: 100
system_prompt:
  zh-TW: |
    你是歷史大叔。
  en: |
    You are the History Uncle.
narration_template:
  zh-TW: |
    {system_prompt}
    介紹 {poi_name}。
    {poi_context}
  en: |
    {system_prompt}
    Tell me about {poi_name}.
    {poi_context}
"""
    yaml_path = tmp_path / "history_uncle.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    cfg = load_persona(yaml_path)
    assert isinstance(cfg, PersonaConfig)
    assert cfg.id == "history_uncle"
    assert cfg.display_name["zh-TW"] == "歷史大叔"
    assert "歷史大叔" in cfg.system_prompt["zh-TW"]


def test_load_all_personas_indexes_by_id(tmp_path: Path):
    (tmp_path / "history_uncle.yaml").write_text("""
id: history_uncle
display_name: {zh-TW: 大叔, en: Uncle}
description: {zh-TW: x, en: x}
voice: {zh-TW: Charon, en: Charon}
poi_source: osm_wikipedia
system_prompt: {zh-TW: x, en: x}
narration_template: {zh-TW: x, en: x}
""", encoding="utf-8")

    personas = load_all_personas(tmp_path)
    assert "history_uncle" in personas
    assert personas["history_uncle"].id == "history_uncle"


def test_load_persona_id_must_match_filename(tmp_path: Path):
    (tmp_path / "history_uncle.yaml").write_text("""
id: not_matching
display_name: {zh-TW: x, en: x}
description: {zh-TW: x, en: x}
voice: {zh-TW: Charon, en: Charon}
poi_source: osm_wikipedia
system_prompt: {zh-TW: x, en: x}
narration_template: {zh-TW: x, en: x}
""", encoding="utf-8")

    with pytest.raises(ValueError, match="filename"):
        load_all_personas(tmp_path)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_persona_loader.py -v
```
Expected: ImportError on `tour_guide.prompts.loader`.

- [ ] **Step 3: Create `backend/src/tour_guide/prompts/__init__.py`**

```python
```
(empty)

- [ ] **Step 4: Create `backend/src/tour_guide/prompts/loader.py`**

```python
"""Persona YAML loader."""
from __future__ import annotations

from pathlib import Path

import yaml

from tour_guide.models.persona import PersonaConfig


def load_persona(yaml_path: Path) -> PersonaConfig:
    """Load a single persona YAML file into a PersonaConfig."""
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return PersonaConfig.model_validate(raw)


def load_all_personas(directory: Path) -> dict[str, PersonaConfig]:
    """Load every *.yaml in `directory`, keyed by persona.id.

    Each persona's id MUST match its filename (without extension).
    """
    out: dict[str, PersonaConfig] = {}
    for yaml_path in sorted(directory.glob("*.yaml")):
        cfg = load_persona(yaml_path)
        if cfg.id != yaml_path.stem:
            raise ValueError(
                f"Persona id '{cfg.id}' does not match filename '{yaml_path.name}'"
            )
        out[cfg.id] = cfg
    return out
```

- [ ] **Step 5: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_persona_loader.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Create `backend/prompts/personas/history_uncle.yaml`**

```yaml
id: history_uncle
display_name:
  zh-TW: 歷史大叔
  en: The History Uncle
description:
  zh-TW: 沉穩深度，年代典故脈絡清楚
  en: Calm and deep, weaving timelines and cultural context

voice:
  zh-TW: Charon
  en: Charon
voice_style:
  speaking_rate: 0.95
  emotion: contemplative

style_profile:
  embellishment: 0.1
  preferred_topics:
    - history
    - cultural_context
  speech_quirks:
    - "根據文獻記載"
    - "在那個年代"
    - "順帶一提"

poi_source: osm_wikipedia
default_trigger_radius_m: 100

system_prompt:
  zh-TW: |
    你是一位精通歷史的中年男性導遊，叫做「歷史大叔」。你的特色：
    - 沉穩、有耐心，講話節奏不疾不徐
    - 重視年代、人物、事件之間的脈絡
    - 喜歡用「在那個年代...」「同時期的...」這類比較拉開時空感
    - 偶爾穿插「根據文獻記載」「順帶一提」這種引子
    - 用詞典雅但不掉書袋，避免艱深學術語

    嚴禁：誇大、捏造未有出處的細節、使用問句結尾賣關子、表演性質的「哇！」「天啊！」
  en: |
    You are a middle-aged male guide called "The History Uncle". Calm, patient,
    measured pacing. Anchor everything in timelines and cultural context. Use
    phrases like "back in that era..." and "you might not know that...". Refined
    but not pretentious. Never fabricate, exaggerate, or use theatrical reactions.

narration_template:
  zh-TW: |
    {system_prompt}

    請根據以下資料，以你的口吻為使用者介紹「{poi_name}」。

    --- POI 背景資料 ---
    {poi_context}
    --- 資料結束 ---

    要求：
    1. 結構為 3 段：簡介 → 重點故事 → 趣聞／延伸
    2. 總長 {target_length}（{target_words} 字左右）
    3. 段落間用空行分隔（讓 TTS 自然停頓）
    4. 嚴禁編造未在背景資料中的具體年代、人名、數字
    5. 若背景資料不足，誠實簡短帶過該段，不要硬掰
  en: |
    {system_prompt}

    Using the data below, introduce "{poi_name}" to the user in your voice.

    --- POI background ---
    {poi_context}
    --- end of data ---

    3 sections (brief intro → key story → fun fact). ~{target_words} words.
    Never fabricate specific dates, names, or numbers. If data is thin, briefly
    acknowledge and move on.

qa_template:
  zh-TW: |
    {system_prompt}

    使用者目前在「{poi_name}」附近，已聽過你的旁白（摘要：{narration_summary}）。
    使用者問：「{user_question}」
    請以你的口吻簡短回答（30-60 秒，~80-150 字）。
    如果問題超出 POI 範圍或你的知識邊界，誠實說「這我不太確定」並引導回 POI 本身。
```

- [ ] **Step 7: Verify the real file loads**

```bash
cd backend && python -c "from pathlib import Path; from tour_guide.prompts.loader import load_all_personas; p = load_all_personas(Path('prompts/personas')); print(list(p.keys()))"
```
Expected: `['history_uncle']`

- [ ] **Step 8: Commit**

```bash
git add backend/src/tour_guide/prompts/ backend/prompts/ backend/tests/unit/test_persona_loader.py
git commit -m "feat(prompts): persona YAML loader + history_uncle persona"
```

---

### Task 7: PromptBuilder — compose narration prompt

**Files:**
- Create: `backend/src/tour_guide/prompts/builder.py`
- Create: `backend/tests/unit/test_prompt_builder.py`

- [ ] **Step 1: Write the failing test**

```python
from tour_guide.prompts.builder import PromptBuilder
from tour_guide.models.persona import PersonaConfig
from tour_guide.models.poi import POI, POIContext, WikiArticle


def _persona() -> PersonaConfig:
    return PersonaConfig(
        id="history_uncle",
        display_name={"zh-TW": "歷史大叔", "en": "The History Uncle"},
        description={"zh-TW": "x", "en": "x"},
        voice={"zh-TW": "Charon", "en": "Charon"},
        poi_source="osm_wikipedia",
        system_prompt={
            "zh-TW": "你是歷史大叔。",
            "en": "You are the History Uncle.",
        },
        narration_template={
            "zh-TW": (
                "{system_prompt}\n\n"
                "介紹「{poi_name}」。\n資料：{poi_context}\n"
                "目標長度：{target_length}（{target_words} 字）"
            ),
            "en": (
                "{system_prompt}\n\nIntroduce '{poi_name}'.\nData: {poi_context}\n"
                "Target length: {target_length} (~{target_words} words)"
            ),
        },
    )


def _poi_context() -> POIContext:
    poi = POI(
        id="osm:way:1",
        name="故宮博物院",
        name_localized="故宮博物院",
        lat=25.1, lon=121.5,
        wiki=WikiArticle(title="故宮博物院", extract="故宮位於台北...", url="http://x"),
        confidence="high",
    )
    return POIContext(poi=poi, background_text="故宮位於台北...", confidence="high")


class TestPromptBuilder:
    def test_build_narration_zh_inserts_persona_and_poi(self):
        msgs = PromptBuilder().build_narration(
            persona=_persona(), poi_ctx=_poi_context(), lang="zh-TW", length="medium"
        )
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        content = msgs[0]["content"]
        assert "你是歷史大叔。" in content
        assert "故宮博物院" in content
        assert "故宮位於台北..." in content
        assert "中等" in content or "medium" in content

    def test_build_narration_en_uses_english_template(self):
        msgs = PromptBuilder().build_narration(
            persona=_persona(), poi_ctx=_poi_context(), lang="en", length="short"
        )
        content = msgs[0]["content"]
        assert "History Uncle" in content
        assert "故宮博物院" in content   # name_localized stays
        assert "short" in content.lower() or "簡" in content

    def test_target_words_scales_with_length(self):
        builder = PromptBuilder()
        short = builder.build_narration(
            persona=_persona(), poi_ctx=_poi_context(), lang="zh-TW", length="short"
        )[0]["content"]
        long_ = builder.build_narration(
            persona=_persona(), poi_ctx=_poi_context(), lang="zh-TW", length="long"
        )[0]["content"]
        # Extract the number after "字" — short < long
        import re
        s_words = int(re.search(r"(\d+)\s*字", short).group(1))
        l_words = int(re.search(r"(\d+)\s*字", long_).group(1))
        assert s_words < l_words
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_prompt_builder.py -v
```
Expected: ImportError on `tour_guide.prompts.builder`.

- [ ] **Step 3: Create `backend/src/tour_guide/prompts/builder.py`**

```python
"""PromptBuilder — composes narration / QA prompts from persona + POI."""
from __future__ import annotations

from typing import Literal

from tour_guide.models.persona import LangCode, NarrationLength, PersonaConfig
from tour_guide.models.poi import POIContext

# Target word count by length, per language
_TARGET_WORDS: dict[tuple[LangCode, NarrationLength], int] = {
    ("zh-TW", "short"): 200,
    ("zh-TW", "medium"): 500,
    ("zh-TW", "long"): 900,
    ("en", "short"): 130,
    ("en", "medium"): 320,
    ("en", "long"): 580,
}

_LENGTH_LABEL: dict[tuple[LangCode, NarrationLength], str] = {
    ("zh-TW", "short"): "簡短（30-60 秒）",
    ("zh-TW", "medium"): "中等（1-3 分鐘）",
    ("zh-TW", "long"): "完整（3-5 分鐘）",
    ("en", "short"): "short (30-60s)",
    ("en", "medium"): "medium (1-3min)",
    ("en", "long"): "long (3-5min)",
}


Message = dict[str, str]   # {"role": "...", "content": "..."}


class PromptBuilder:
    """Composes prompt messages for the LLM. Pure (no IO)."""

    def build_narration(
        self,
        *,
        persona: PersonaConfig,
        poi_ctx: POIContext,
        lang: LangCode,
        length: NarrationLength,
    ) -> list[Message]:
        template = persona.narration_template[lang]
        system_prompt = persona.system_prompt[lang]
        content = template.format(
            system_prompt=system_prompt,
            poi_name=poi_ctx.poi.name_localized,
            poi_context=poi_ctx.background_text,
            target_length=_LENGTH_LABEL[(lang, length)],
            target_words=_TARGET_WORDS[(lang, length)],
        )
        return [{"role": "user", "content": content}]
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_prompt_builder.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/prompts/builder.py backend/tests/unit/test_prompt_builder.py
git commit -m "feat(prompts): PromptBuilder for narration prompts (zh-TW + en)"
```

---

### Task 8: ConfidenceClassifier

**Files:**
- Create: `backend/src/tour_guide/services/__init__.py`
- Create: `backend/src/tour_guide/services/confidence.py`
- Create: `backend/tests/unit/test_confidence.py`

- [ ] **Step 1: Write the failing test**

```python
from tour_guide.services.confidence import classify
from tour_guide.models.poi import POI, WikiArticle


def _poi(name: str = "X", wiki_extract: str | None = None, tags: dict | None = None) -> POI:
    return POI(
        id="osm:way:1",
        name=name,
        name_localized=name,
        lat=0, lon=0,
        tags=tags or {},
        wiki=WikiArticle(title=name, extract=wiki_extract, url="x") if wiki_extract else None,
    )


class TestClassify:
    def test_high_when_wiki_extract_at_least_200_chars(self):
        long_text = "abc" * 100   # 300 chars
        assert classify(_poi(wiki_extract=long_text)) == "high"

    def test_medium_when_wiki_extract_below_threshold(self):
        assert classify(_poi(wiki_extract="too short")) == "medium"

    def test_medium_when_no_wiki_but_strong_osm_tag(self):
        assert classify(_poi(tags={"tourism": "museum"})) == "medium"
        assert classify(_poi(tags={"historic": "monument"})) == "medium"

    def test_low_when_no_wiki_and_no_strong_tag(self):
        assert classify(_poi(tags={"shop": "convenience"})) == "low"
        assert classify(_poi(tags={})) == "low"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_confidence.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/services/__init__.py`**

```python
```
(empty)

- [ ] **Step 4: Create `backend/src/tour_guide/services/confidence.py`**

```python
"""ConfidenceClassifier — pure function determining narration confidence level."""
from __future__ import annotations

from tour_guide.models.poi import POI, Confidence

_WIKI_HIGH_THRESHOLD_CHARS = 200

_STRONG_TAG_KEYS = {"tourism", "historic"}
_STRONG_TAG_VALUES = {
    "museum", "attraction", "gallery", "viewpoint", "monument", "artwork",
    "yes", "memorial", "ruins", "castle", "fort",
}


def classify(poi: POI) -> Confidence:
    """Classify confidence level based on data richness."""
    if poi.wiki and poi.wiki.extract and len(poi.wiki.extract) >= _WIKI_HIGH_THRESHOLD_CHARS:
        return "high"

    if poi.wiki and poi.wiki.extract:
        return "medium"

    for k, v in poi.tags.items():
        if k in _STRONG_TAG_KEYS and v in _STRONG_TAG_VALUES:
            return "medium"

    return "low"
```

- [ ] **Step 5: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_confidence.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/services/ backend/tests/unit/test_confidence.py
git commit -m "feat(services): ConfidenceClassifier (high/medium/low based on wiki + tags)"
```

---

### Task 9: LlmProvider interface + FakeLlmProvider

**Files:**
- Create: `backend/src/tour_guide/providers/__init__.py`
- Create: `backend/src/tour_guide/providers/llm.py`
- Create: `backend/src/tour_guide/providers/fakes.py`

- [ ] **Step 1: Create `backend/src/tour_guide/providers/__init__.py`**

```python
```
(empty)

- [ ] **Step 2: Create `backend/src/tour_guide/providers/llm.py`**

```python
"""LLM provider abstraction."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class LlmProvider(Protocol):
    """Stream chat completion text chunks."""

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Yield text chunks as the LLM generates them."""
        ...
```

- [ ] **Step 3: Create `backend/src/tour_guide/providers/fakes.py`**

```python
"""Fake provider implementations for offline tests."""
from __future__ import annotations

from collections.abc import AsyncIterator


class FakeLlmProvider:
    """Yields predefined chunks regardless of input."""

    def __init__(self, scripted_chunks: list[str]) -> None:
        self._chunks = scripted_chunks
        self.calls: list[dict] = []

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        self.calls.append({"messages": messages, "model": model})
        for c in self._chunks:
            yield c
```

- [ ] **Step 4: Quick smoke test**

```bash
cd backend && python -c "
import asyncio
from tour_guide.providers.fakes import FakeLlmProvider

async def main():
    p = FakeLlmProvider(['hello ', 'world.'])
    chunks = [c async for c in p.chat_stream(messages=[], model='x')]
    print(chunks)

asyncio.run(main())
"
```
Expected: `['hello ', 'world.']`

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/providers/
git commit -m "feat(providers): LlmProvider Protocol + FakeLlmProvider"
```

---

### Task 10: TtsProvider interface + FakeTtsProvider

**Files:**
- Create: `backend/src/tour_guide/providers/tts.py`
- Modify: `backend/src/tour_guide/providers/fakes.py`

- [ ] **Step 1: Create `backend/src/tour_guide/providers/tts.py`**

```python
"""TTS provider abstraction."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class TtsProvider(Protocol):
    """Synthesize text to audio bytes (mp3 or opus, provider-defined)."""

    async def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        speaking_rate: float = 1.0,
        emotion: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Yield audio chunk bytes for the given text."""
        ...
```

- [ ] **Step 2: Append `FakeTtsProvider` to `backend/src/tour_guide/providers/fakes.py`**

```python
class FakeTtsProvider:
    """Returns a deterministic 4-byte chunk per call. Records inputs."""

    def __init__(self, fake_chunk: bytes = b"AUDI") -> None:
        self._chunk = fake_chunk
        self.calls: list[dict] = []

    async def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        speaking_rate: float = 1.0,
        emotion: str | None = None,
    ) -> AsyncIterator[bytes]:
        self.calls.append({"text": text, "voice_id": voice_id})
        yield self._chunk
```

- [ ] **Step 3: Smoke test**

```bash
cd backend && python -c "
import asyncio
from tour_guide.providers.fakes import FakeTtsProvider

async def main():
    p = FakeTtsProvider()
    chunks = [c async for c in p.synthesize(text='hi', voice_id='Charon')]
    print(chunks, p.calls)

asyncio.run(main())
"
```
Expected: `[b'AUDI'] [{'text': 'hi', 'voice_id': 'Charon'}]`

- [ ] **Step 4: Commit**

```bash
git add backend/src/tour_guide/providers/
git commit -m "feat(providers): TtsProvider Protocol + FakeTtsProvider"
```

---

### Task 11: NarrationService — orchestrate prompt → LLM → splitter → TTS (with fakes)

**Files:**
- Create: `backend/src/tour_guide/services/narration_service.py`
- Create: `backend/tests/unit/test_narration_service.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from tour_guide.providers.fakes import FakeLlmProvider, FakeTtsProvider
from tour_guide.prompts.builder import PromptBuilder
from tour_guide.services.narration_service import NarrationService, NarrationEvent
from tour_guide.models.persona import PersonaConfig, VoiceStyle
from tour_guide.models.poi import POI, POIContext, WikiArticle


def _persona() -> PersonaConfig:
    return PersonaConfig(
        id="history_uncle",
        display_name={"zh-TW": "歷史大叔", "en": "Uncle"},
        description={"zh-TW": "x", "en": "x"},
        voice={"zh-TW": "Charon", "en": "Charon"},
        voice_style=VoiceStyle(speaking_rate=0.95),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是歷史大叔。", "en": "x"},
        narration_template={
            "zh-TW": "{system_prompt}\n介紹 {poi_name}。{poi_context} 長 {target_length} {target_words}",
            "en": "{system_prompt}\n{poi_name} {poi_context} {target_length} {target_words}",
        },
    )


def _poi_ctx() -> POIContext:
    poi = POI(
        id="osm:way:1", name="故宮", name_localized="故宮",
        lat=25.1, lon=121.5,
        wiki=WikiArticle(title="故宮", extract="故宮位於台北" * 30, url="x"),
        confidence="high",
    )
    return POIContext(poi=poi, background_text="背景資料", confidence="high")


@pytest.mark.asyncio
async def test_narration_emits_meta_then_text_audio_then_end():
    llm = FakeLlmProvider(["故宮位於", "台北。它建於", "1925 年。"])
    tts = FakeTtsProvider(fake_chunk=b"AAAA")
    svc = NarrationService(
        llm=llm, tts=tts, prompt_builder=PromptBuilder(),
        llm_model="gemini/gemini-2.5-flash",
    )

    events: list[NarrationEvent] = []
    async for ev in svc.narrate(
        persona=_persona(), poi_ctx=_poi_ctx(), lang="zh-TW", length="medium"
    ):
        events.append(ev)

    types = [e.type for e in events]
    assert types[0] == "meta"
    assert "end" in types
    assert types.count("text") >= 1
    assert types.count("audio") >= 2  # at least 2 sentences synthesized

    # meta carries confidence
    assert events[0].data["confidence"] == "high"

    # final end event
    assert types[-1] == "end"


@pytest.mark.asyncio
async def test_narration_handles_text_with_no_terminator_via_flush():
    llm = FakeLlmProvider(["沒有句點的尾巴"])
    tts = FakeTtsProvider()
    svc = NarrationService(
        llm=llm, tts=tts, prompt_builder=PromptBuilder(),
        llm_model="gemini/gemini-2.5-flash",
    )

    events = [e async for e in svc.narrate(
        persona=_persona(), poi_ctx=_poi_ctx(), lang="zh-TW", length="short"
    )]
    types = [e.type for e in events]
    assert "audio" in types  # flush triggered TTS
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_narration_service.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/services/narration_service.py`**

```python
"""NarrationService — orchestrates the streaming narration pipeline."""
from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from tour_guide.models.persona import LangCode, NarrationLength, PersonaConfig
from tour_guide.models.poi import POIContext
from tour_guide.pipeline.sentence_splitter import StreamingSentenceBuffer
from tour_guide.prompts.builder import PromptBuilder
from tour_guide.providers.llm import LlmProvider
from tour_guide.providers.tts import TtsProvider


@dataclass
class NarrationEvent:
    type: str            # "meta" | "text" | "audio" | "end" | "error"
    data: dict[str, Any] = field(default_factory=dict)


class NarrationService:
    def __init__(
        self,
        *,
        llm: LlmProvider,
        tts: TtsProvider,
        prompt_builder: PromptBuilder,
        llm_model: str,
    ) -> None:
        self._llm = llm
        self._tts = tts
        self._prompt_builder = prompt_builder
        self._llm_model = llm_model

    async def narrate(
        self,
        *,
        persona: PersonaConfig,
        poi_ctx: POIContext,
        lang: LangCode,
        length: NarrationLength,
    ) -> AsyncIterator[NarrationEvent]:
        # 1. meta event
        yield NarrationEvent(type="meta", data={
            "poi_id": poi_ctx.poi.id,
            "confidence": poi_ctx.confidence,
            "persona": persona.id,
            "lang": lang,
        })

        # 2. build prompt + start LLM stream
        messages = self._prompt_builder.build_narration(
            persona=persona, poi_ctx=poi_ctx, lang=lang, length=length
        )
        voice_id = persona.voice[lang]

        buf = StreamingSentenceBuffer()
        sentence_idx = 0

        async for text_chunk in self._llm.chat_stream(
            messages=messages, model=self._llm_model
        ):
            yield NarrationEvent(type="text", data={"chunk": text_chunk})
            for sentence in buf.feed(text_chunk):
                async for audio_chunk in self._tts.synthesize(
                    text=sentence,
                    voice_id=voice_id,
                    speaking_rate=persona.voice_style.speaking_rate,
                    emotion=persona.voice_style.emotion,
                ):
                    yield NarrationEvent(type="audio", data={
                        "chunk_b64": base64.b64encode(audio_chunk).decode("ascii"),
                        "sentence_idx": sentence_idx,
                    })
                sentence_idx += 1

        # 3. flush any tail
        for sentence in buf.flush():
            async for audio_chunk in self._tts.synthesize(
                text=sentence,
                voice_id=voice_id,
                speaking_rate=persona.voice_style.speaking_rate,
                emotion=persona.voice_style.emotion,
            ):
                yield NarrationEvent(type="audio", data={
                    "chunk_b64": base64.b64encode(audio_chunk).decode("ascii"),
                    "sentence_idx": sentence_idx,
                })
            sentence_idx += 1

        yield NarrationEvent(type="end", data={"sentences": sentence_idx})
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_narration_service.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/narration_service.py backend/tests/unit/test_narration_service.py
git commit -m "feat(services): NarrationService — streaming prompt → LLM → splitter → TTS"
```

---

### Task 12: WikipediaClient — fetch summary

**Files:**
- Create: `backend/src/tour_guide/clients/__init__.py`
- Create: `backend/src/tour_guide/clients/wikipedia.py`
- Create: `backend/tests/unit/test_wikipedia_client.py`

- [ ] **Step 1: Write the failing test**

```python
import httpx
import pytest
import respx

from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.models.poi import WikiArticle


@pytest.mark.asyncio
async def test_summary_returns_wiki_article(respx_mock: respx.MockRouter):
    respx_mock.get("https://zh.wikipedia.org/api/rest_v1/page/summary/%E6%95%85%E5%AE%AE").mock(
        return_value=httpx.Response(200, json={
            "title": "故宮博物院",
            "extract": "故宮博物院位於台北市士林區...",
            "content_urls": {"desktop": {"page": "https://zh.wikipedia.org/wiki/故宮"}},
            "type": "standard",
        })
    )

    async with httpx.AsyncClient() as client:
        wc = WikipediaClient(client)
        article = await wc.summary(title="故宮", lang="zh-TW")

    assert isinstance(article, WikiArticle)
    assert article.title == "故宮博物院"
    assert "故宮" in article.extract


@pytest.mark.asyncio
async def test_summary_returns_none_for_disambiguation(respx_mock: respx.MockRouter):
    respx_mock.get("https://en.wikipedia.org/api/rest_v1/page/summary/Mercury").mock(
        return_value=httpx.Response(200, json={
            "title": "Mercury",
            "extract": "...",
            "type": "disambiguation",
            "content_urls": {"desktop": {"page": "x"}},
        })
    )

    async with httpx.AsyncClient() as client:
        wc = WikipediaClient(client)
        article = await wc.summary(title="Mercury", lang="en")

    assert article is None


@pytest.mark.asyncio
async def test_summary_returns_none_on_404(respx_mock: respx.MockRouter):
    respx_mock.get("https://zh.wikipedia.org/api/rest_v1/page/summary/Nope").mock(
        return_value=httpx.Response(404)
    )

    async with httpx.AsyncClient() as client:
        wc = WikipediaClient(client)
        article = await wc.summary(title="Nope", lang="zh-TW")

    assert article is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_wikipedia_client.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/clients/__init__.py`**

```python
```
(empty)

- [ ] **Step 4: Create `backend/src/tour_guide/clients/wikipedia.py`**

```python
"""Wikipedia REST API client (summary endpoint)."""
from __future__ import annotations

from urllib.parse import quote

import httpx

from tour_guide.models.persona import LangCode
from tour_guide.models.poi import WikiArticle

_LANG_HOST: dict[LangCode, str] = {
    "zh-TW": "zh.wikipedia.org",
    "en": "en.wikipedia.org",
}


class WikipediaClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def summary(self, *, title: str, lang: LangCode) -> WikiArticle | None:
        host = _LANG_HOST[lang]
        url = f"https://{host}/api/rest_v1/page/summary/{quote(title)}"

        try:
            r = await self._client.get(url, timeout=10.0)
        except httpx.RequestError:
            return None

        if r.status_code != 200:
            return None

        data = r.json()
        if data.get("type") == "disambiguation":
            return None

        extract = data.get("extract")
        if not extract:
            return None

        page_url = (
            data.get("content_urls", {}).get("desktop", {}).get("page")
            or f"https://{host}/wiki/{quote(title)}"
        )
        return WikiArticle(title=data["title"], extract=extract, url=page_url)
```

- [ ] **Step 5: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_wikipedia_client.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/clients/ backend/tests/unit/test_wikipedia_client.py
git commit -m "feat(clients): WikipediaClient.summary"
```

---

### Task 13: OverpassClient — query nearby POIs

**Files:**
- Create: `backend/src/tour_guide/clients/overpass.py`
- Create: `backend/tests/unit/test_overpass_client.py`

- [ ] **Step 1: Write the failing test**

```python
import httpx
import pytest
import respx

from tour_guide.clients.overpass import OverpassClient


@pytest.mark.asyncio
async def test_nearby_returns_poi_list(respx_mock: respx.MockRouter):
    respx_mock.post("https://overpass-api.de/api/interpreter").mock(
        return_value=httpx.Response(200, json={
            "elements": [
                {
                    "type": "way", "id": 12345,
                    "center": {"lat": 25.1023, "lon": 121.5482},
                    "tags": {
                        "name": "國立故宮博物院",
                        "name:en": "National Palace Museum",
                        "tourism": "museum",
                        "wikidata": "Q193375",
                        "wikipedia": "zh:國立故宮博物院",
                    },
                },
                {
                    "type": "node", "id": 99,
                    "lat": 25.1, "lon": 121.5,
                    "tags": {"shop": "convenience"},   # should be filtered out
                },
            ]
        })
    )

    async with httpx.AsyncClient() as client:
        oc = OverpassClient(client)
        results = await oc.nearby(lat=25.1023, lon=121.5482, radius_m=500)

    assert len(results) == 1
    assert results[0].id == "osm:way:12345"
    assert results[0].name == "國立故宮博物院"
    assert results[0].tags["tourism"] == "museum"


@pytest.mark.asyncio
async def test_nearby_returns_empty_on_503(respx_mock: respx.MockRouter):
    respx_mock.post("https://overpass-api.de/api/interpreter").mock(
        return_value=httpx.Response(503)
    )

    async with httpx.AsyncClient() as client:
        oc = OverpassClient(client)
        results = await oc.nearby(lat=0, lon=0, radius_m=100)

    assert results == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_overpass_client.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/clients/overpass.py`**

```python
"""Overpass API client — queries OSM POIs by location."""
from __future__ import annotations

import httpx

from tour_guide.models.poi import POI

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_INCLUDED_KEYS_VALUES = (
    ("tourism", "museum|attraction|gallery|viewpoint|monument|artwork|memorial"),
    ("historic", "."),   # any value
    ("building", "temple|cathedral|mosque|synagogue"),
    ("leisure", "park"),
)


def _build_query(lat: float, lon: float, radius_m: int) -> str:
    around = f"around:{radius_m},{lat},{lon}"
    parts = []
    for key, val_re in _INCLUDED_KEYS_VALUES:
        parts.append(f'  nwr["{key}"~"^({val_re})$"]({around});')
    body = "\n".join(parts)
    return f"[out:json][timeout:25];\n(\n{body}\n);\nout center tags;"


def _name_localized(tags: dict[str, str]) -> str:
    return tags.get("name:zh") or tags.get("name") or tags.get("int_name") or "(unnamed)"


class OverpassClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def nearby(self, *, lat: float, lon: float, radius_m: int) -> list[POI]:
        query = _build_query(lat, lon, radius_m)
        try:
            r = await self._client.post(
                _OVERPASS_URL, data={"data": query}, timeout=30.0
            )
        except httpx.RequestError:
            return []
        if r.status_code != 200:
            return []

        out: list[POI] = []
        for el in r.json().get("elements", []):
            tags = el.get("tags") or {}
            if not tags.get("name"):
                continue

            elat = el.get("lat") or el.get("center", {}).get("lat")
            elon = el.get("lon") or el.get("center", {}).get("lon")
            if elat is None or elon is None:
                continue

            poi_id = f"osm:{el['type']}:{el['id']}"
            out.append(POI(
                id=poi_id,
                name=tags["name"],
                name_localized=_name_localized(tags),
                lat=elat, lon=elon,
                tags=tags,
            ))
        return out
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_overpass_client.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/clients/overpass.py backend/tests/unit/test_overpass_client.py
git commit -m "feat(clients): OverpassClient.nearby (OSM POI lookup)"
```

---

### Task 14: POI filter logic (whitelist + wiki tag)

**Files:**
- Create: `backend/src/tour_guide/services/poi_filter.py`
- Create: `backend/tests/unit/test_poi_filter.py`

- [ ] **Step 1: Write the failing test**

```python
from tour_guide.models.poi import POI
from tour_guide.services.poi_filter import is_narratable


def _poi(tags: dict) -> POI:
    return POI(id="osm:way:1", name="X", name_localized="X", lat=0, lon=0, tags=tags)


class TestIsNarratable:
    def test_with_wiki_tag_is_narratable(self):
        assert is_narratable(_poi({"tourism": "museum", "wikipedia": "zh:故宮"}))

    def test_with_wikidata_tag_is_narratable(self):
        assert is_narratable(_poi({"historic": "monument", "wikidata": "Q123"}))

    def test_without_wiki_tag_is_not_narratable(self):
        assert not is_narratable(_poi({"tourism": "museum"}))

    def test_strong_tag_required_even_with_wiki(self):
        assert not is_narratable(_poi({"shop": "supermarket", "wikipedia": "zh:Foo"}))
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_poi_filter.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/services/poi_filter.py`**

```python
"""POI filter — narratability rules for the 通用式 (OSM/Wiki) flow."""
from __future__ import annotations

from tour_guide.models.poi import POI

_STRONG_TAG_KEYS = {"tourism", "historic", "building", "leisure"}


def is_narratable(poi: POI) -> bool:
    """A POI is narratable iff it has both a strong tag AND a wiki/wikidata link."""
    has_wiki = "wikipedia" in poi.tags or "wikidata" in poi.tags
    has_strong_tag = any(k in _STRONG_TAG_KEYS for k in poi.tags)
    return has_wiki and has_strong_tag
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_poi_filter.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/poi_filter.py backend/tests/unit/test_poi_filter.py
git commit -m "feat(services): is_narratable POI filter (strong tag + wiki/wikidata)"
```

---

### Task 15: POIService.nearby — combine Overpass + Wikipedia + filter + classify

**Files:**
- Create: `backend/src/tour_guide/services/poi_service.py`
- Create: `backend/tests/unit/test_poi_service.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from tour_guide.models.poi import POI, WikiArticle
from tour_guide.services.poi_service import POIService


class _FakeOverpass:
    def __init__(self, results: list[POI]) -> None:
        self._results = results
        self.calls = []

    async def nearby(self, *, lat, lon, radius_m):
        self.calls.append({"lat": lat, "lon": lon, "radius_m": radius_m})
        return self._results


class _FakeWiki:
    def __init__(self, articles: dict[str, WikiArticle | None]) -> None:
        self._articles = articles
        self.calls = []

    async def summary(self, *, title, lang):
        self.calls.append({"title": title, "lang": lang})
        return self._articles.get(title)


@pytest.mark.asyncio
async def test_nearby_attaches_wiki_and_classifies():
    overpass = _FakeOverpass([
        POI(id="osm:way:1", name="故宮", name_localized="故宮", lat=25.1, lon=121.5,
            tags={"tourism": "museum", "wikipedia": "zh:故宮博物院"}),
        POI(id="osm:way:2", name="無 wiki", name_localized="無 wiki", lat=0, lon=0,
            tags={"tourism": "museum"}),   # filtered out
    ])
    wiki = _FakeWiki({
        "故宮博物院": WikiArticle(title="故宮博物院", extract="長文" * 100, url="x"),
    })

    svc = POIService(overpass=overpass, wikipedia=wiki)
    pois = await svc.nearby(lat=25.1, lon=121.5, radius_m=500, lang="zh-TW")

    assert len(pois) == 1
    assert pois[0].id == "osm:way:1"
    assert pois[0].wiki is not None
    assert pois[0].confidence == "high"


@pytest.mark.asyncio
async def test_nearby_distance_calculated():
    overpass = _FakeOverpass([
        POI(id="osm:way:1", name="X", name_localized="X", lat=25.1023, lon=121.5482,
            tags={"tourism": "museum", "wikipedia": "zh:X"}),
    ])
    wiki = _FakeWiki({"X": WikiArticle(title="X", extract="x" * 300, url="y")})
    svc = POIService(overpass=overpass, wikipedia=wiki)

    pois = await svc.nearby(lat=25.1023, lon=121.5482, radius_m=500, lang="zh-TW")
    assert pois[0].distance_m == 0


@pytest.mark.asyncio
async def test_nearby_handles_wiki_lookup_failure_gracefully():
    overpass = _FakeOverpass([
        POI(id="osm:way:1", name="故宮", name_localized="故宮", lat=0, lon=0,
            tags={"tourism": "museum", "wikipedia": "zh:故宮"}),
    ])
    wiki = _FakeWiki({})   # no article

    svc = POIService(overpass=overpass, wikipedia=wiki)
    pois = await svc.nearby(lat=0, lon=0, radius_m=500, lang="zh-TW")
    assert pois[0].wiki is None
    assert pois[0].confidence == "medium"   # has tourism=museum strong tag
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_poi_service.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/services/poi_service.py`**

```python
"""POIService — combines Overpass + Wikipedia + filter + confidence."""
from __future__ import annotations

import math
from typing import Protocol

from tour_guide.models.persona import LangCode
from tour_guide.models.poi import POI, POIContext, WikiArticle
from tour_guide.services.confidence import classify
from tour_guide.services.poi_filter import is_narratable


class _OverpassLike(Protocol):
    async def nearby(self, *, lat: float, lon: float, radius_m: int) -> list[POI]: ...


class _WikipediaLike(Protocol):
    async def summary(self, *, title: str, lang: LangCode) -> WikiArticle | None: ...


def _haversine_m(lat1, lon1, lat2, lon2) -> int:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(2 * R * math.asin(math.sqrt(a)))


def _wiki_title_from_tag(tag_value: str) -> str:
    """OSM `wikipedia` tag is e.g. 'zh:故宮博物院' — strip the lang prefix."""
    if ":" in tag_value:
        return tag_value.split(":", 1)[1]
    return tag_value


class POIService:
    def __init__(self, *, overpass: _OverpassLike, wikipedia: _WikipediaLike) -> None:
        self._overpass = overpass
        self._wikipedia = wikipedia

    async def nearby(
        self, *, lat: float, lon: float, radius_m: int, lang: LangCode
    ) -> list[POI]:
        raw_pois = await self._overpass.nearby(lat=lat, lon=lon, radius_m=radius_m)
        narratable = [p for p in raw_pois if is_narratable(p)]

        out: list[POI] = []
        for poi in narratable:
            wiki_tag = poi.tags.get("wikipedia")
            article = None
            if wiki_tag:
                title = _wiki_title_from_tag(wiki_tag)
                article = await self._wikipedia.summary(title=title, lang=lang)

            poi.wiki = article
            poi.distance_m = _haversine_m(lat, lon, poi.lat, poi.lon)
            poi.confidence = classify(poi)
            out.append(poi)

        out.sort(key=lambda p: p.distance_m or 0)
        return out

    async def context(self, poi: POI) -> POIContext:
        bg = poi.wiki.extract if poi.wiki else f"{poi.name_localized}（{', '.join(f'{k}={v}' for k, v in poi.tags.items())}）"
        return POIContext(poi=poi, background_text=bg, confidence=poi.confidence)
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_poi_service.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/poi_service.py backend/tests/unit/test_poi_service.py
git commit -m "feat(services): POIService.nearby + .context (overpass + wiki + filter + confidence)"
```

---

### Task 16: AppConfig (pydantic-settings)

**Files:**
- Create: `backend/src/tour_guide/config.py`
- Create: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
import os
from pathlib import Path

import pytest

from tour_guide.config import AppConfig


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    monkeypatch.setenv("PORT", "9999")
    cfg = AppConfig()
    assert cfg.gemini_api_key == "abc"
    assert cfg.port == 9999


def test_persona_dir_default_is_relative_to_repo():
    cfg = AppConfig(gemini_api_key="x")
    assert cfg.persona_dir.name == "personas"


def test_cache_dirs_default_under_tmp():
    cfg = AppConfig(gemini_api_key="x")
    assert "tour_guide" in str(cfg.poi_cache_dir)
    assert "narration" in str(cfg.narration_cache_dir)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_config.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/config.py`**

```python
"""AppConfig — env-driven configuration."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = Field(..., description="Google AI Studio Gemini API key")

    host: str = "0.0.0.0"
    port: int = 8000

    persona_dir: Path = Path(__file__).resolve().parent.parent.parent / "prompts" / "personas"
    poi_cache_dir: Path = Path("/tmp/tour_guide_cache")
    narration_cache_dir: Path = Path("/tmp/tour_guide_narration_cache")

    llm_model: str = "gemini/gemini-2.5-flash"
    tts_model: str = "gemini-2.5-flash-preview-tts"
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_config.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/config.py backend/tests/unit/test_config.py
git commit -m "feat(config): AppConfig env-driven settings"
```

---

### Task 17: SSE event encoding

**Files:**
- Create: `backend/src/tour_guide/api/__init__.py`
- Create: `backend/src/tour_guide/api/sse.py`
- Create: `backend/tests/unit/test_sse.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from tour_guide.api.sse import event_to_sse, NarrationEvent


def test_event_to_sse_formats_correctly():
    ev = NarrationEvent(type="text", data={"chunk": "hi"})
    s = event_to_sse(ev)
    assert s.startswith("event: text\n")
    assert "data: " in s
    payload = s.split("data: ", 1)[1].rstrip("\n\n")
    assert json.loads(payload) == {"chunk": "hi"}
    assert s.endswith("\n\n")


def test_meta_event_with_complex_payload():
    ev = NarrationEvent(type="meta", data={"poi_id": "x", "confidence": "high"})
    assert "event: meta" in event_to_sse(ev)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_sse.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/api/__init__.py`**

```python
```
(empty)

- [ ] **Step 4: Create `backend/src/tour_guide/api/sse.py`**

```python
"""SSE encoding helpers."""
from __future__ import annotations

import json

# Re-export so callers don't need to import from services
from tour_guide.services.narration_service import NarrationEvent  # noqa: F401


def event_to_sse(event: NarrationEvent) -> str:
    """Format a NarrationEvent as a single SSE message."""
    payload = json.dumps(event.data, ensure_ascii=False)
    return f"event: {event.type}\ndata: {payload}\n\n"
```

- [ ] **Step 5: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_sse.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/api/ backend/tests/unit/test_sse.py
git commit -m "feat(api): SSE event encoding helper"
```

---

### Task 18: /health endpoint

**Files:**
- Create: `backend/src/tour_guide/api/health.py`
- Create: `backend/tests/integration/test_health_api.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tour_guide.api.health import router as health_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    return app


def test_health_returns_ok():
    client = TestClient(_app())
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "uptime_s" in body
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/integration/test_health_api.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/api/health.py`**

```python
"""GET /health — service health probe."""
from __future__ import annotations

import time

from fastapi import APIRouter

router = APIRouter()
_STARTED_AT = time.monotonic()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "uptime_s": int(time.monotonic() - _STARTED_AT)}
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/integration/test_health_api.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/api/health.py backend/tests/integration/test_health_api.py
git commit -m "feat(api): GET /health endpoint"
```

---

### Task 19: /poi/nearby endpoint

**Files:**
- Create: `backend/src/tour_guide/api/poi.py`
- Create: `backend/tests/integration/test_poi_api.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tour_guide.api.poi import router as poi_router, get_poi_service
from tour_guide.models.poi import POI, WikiArticle
from tour_guide.services.poi_service import POIService


class _FakePoiService(POIService):
    def __init__(self, results):
        self._results = results

    async def nearby(self, *, lat, lon, radius_m, lang):
        return self._results


def _app(svc) -> FastAPI:
    app = FastAPI()
    app.include_router(poi_router)
    app.dependency_overrides[get_poi_service] = lambda: svc
    return app


def test_poi_nearby_returns_serialized_pois():
    poi = POI(
        id="osm:way:1", name="故宮", name_localized="故宮", lat=25.1, lon=121.5,
        tags={"tourism": "museum", "wikipedia": "zh:故宮"},
        wiki=WikiArticle(title="故宮", extract="x" * 300, url="http://x"),
        distance_m=42, confidence="high",
    )
    client = TestClient(_app(_FakePoiService([poi])))
    r = client.get("/poi/nearby?lat=25.1&lon=121.5&radius=500&lang=zh-TW")
    assert r.status_code == 200
    body = r.json()
    assert len(body["pois"]) == 1
    assert body["pois"][0]["id"] == "osm:way:1"
    assert body["pois"][0]["confidence"] == "high"
    assert body["pois"][0]["distance_m"] == 42


def test_poi_nearby_validates_lat_lon():
    client = TestClient(_app(_FakePoiService([])))
    r = client.get("/poi/nearby?lat=999&lon=0&radius=500&lang=zh-TW")
    assert r.status_code == 422
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/integration/test_poi_api.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/api/poi.py`**

```python
"""GET /poi/nearby — nearby POI lookup."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from tour_guide.models.persona import LangCode
from tour_guide.services.poi_service import POIService

router = APIRouter()


def get_poi_service() -> POIService:
    """Dependency stub — overridden by main.py at app startup."""
    raise NotImplementedError("POIService dependency not wired")


@router.get("/poi/nearby")
async def nearby(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius: Annotated[int, Query(ge=10, le=2000)] = 500,
    lang: Annotated[LangCode, Query()] = "zh-TW",
    svc: Annotated[POIService, Depends(get_poi_service)] = None,
) -> dict:
    pois = await svc.nearby(lat=lat, lon=lon, radius_m=radius, lang=lang)
    return {
        "pois": [p.model_dump() for p in pois],
        "queried_at": datetime.now(tz=timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/integration/test_poi_api.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/api/poi.py backend/tests/integration/test_poi_api.py
git commit -m "feat(api): GET /poi/nearby endpoint"
```

---

### Task 20: /narration SSE endpoint (with fake providers)

**Files:**
- Create: `backend/src/tour_guide/api/narration.py`
- Create: `backend/tests/integration/test_narration_api.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tour_guide.api.narration import (
    router as narration_router,
    get_narration_service,
    get_personas,
    get_poi_service,
)
from tour_guide.models.persona import PersonaConfig, VoiceStyle
from tour_guide.models.poi import POI, POIContext, WikiArticle
from tour_guide.providers.fakes import FakeLlmProvider, FakeTtsProvider
from tour_guide.prompts.builder import PromptBuilder
from tour_guide.services.narration_service import NarrationService


def _persona() -> PersonaConfig:
    return PersonaConfig(
        id="history_uncle",
        display_name={"zh-TW": "歷史大叔", "en": "Uncle"},
        description={"zh-TW": "x", "en": "x"},
        voice={"zh-TW": "Charon", "en": "Charon"},
        voice_style=VoiceStyle(),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是大叔。", "en": "x"},
        narration_template={
            "zh-TW": "{system_prompt}\n{poi_name}\n{poi_context}\n{target_length}\n{target_words}",
            "en": "{system_prompt}\n{poi_name}\n{poi_context}\n{target_length}\n{target_words}",
        },
    )


class _FakePoiService:
    async def nearby(self, **k): return []
    async def context(self, poi: POI) -> POIContext:
        return POIContext(poi=poi, background_text="背景文", confidence="high")


def _app() -> tuple[FastAPI, FakeLlmProvider, FakeTtsProvider]:
    llm = FakeLlmProvider(["第一句話。", "第二句話。"])
    tts = FakeTtsProvider(b"AAAA")
    svc = NarrationService(
        llm=llm, tts=tts, prompt_builder=PromptBuilder(),
        llm_model="gemini/test",
    )

    app = FastAPI()
    app.include_router(narration_router)
    app.dependency_overrides[get_narration_service] = lambda: svc
    app.dependency_overrides[get_personas] = lambda: {"history_uncle": _persona()}
    app.dependency_overrides[get_poi_service] = lambda: _FakePoiService()
    return app, llm, tts


def _parse_sse(body: str) -> list[dict[str, Any]]:
    out = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        ev_line, data_line = block.split("\n", 1)
        ev_type = ev_line.removeprefix("event: ")
        payload = json.loads(data_line.removeprefix("data: "))
        out.append({"type": ev_type, "data": payload})
    return out


def test_narration_streams_meta_text_audio_end():
    app, _, _ = _app()
    client = TestClient(app)

    payload = {
        "poi": {
            "id": "osm:way:1", "name": "故宮", "name_localized": "故宮",
            "lat": 25.1, "lon": 121.5,
            "tags": {"tourism": "museum"},
        },
        "persona": "history_uncle",
        "lang": "zh-TW",
        "length": "medium",
    }
    with client.stream("POST", "/narration", json=payload) as r:
        assert r.status_code == 200
        body = r.read().decode("utf-8")

    events = _parse_sse(body)
    types = [e["type"] for e in events]
    assert types[0] == "meta"
    assert "audio" in types
    assert types[-1] == "end"


def test_narration_unknown_persona_returns_400():
    app, _, _ = _app()
    client = TestClient(app)
    payload = {
        "poi": {
            "id": "osm:way:1", "name": "故宮", "name_localized": "故宮",
            "lat": 25.1, "lon": 121.5, "tags": {},
        },
        "persona": "nonexistent",
        "lang": "zh-TW",
        "length": "medium",
    }
    r = client.post("/narration", json=payload)
    assert r.status_code == 400
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/integration/test_narration_api.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/api/narration.py`**

```python
"""POST /narration — SSE-streamed narration."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from tour_guide.api.sse import event_to_sse
from tour_guide.models.persona import LangCode, NarrationLength, PersonaConfig
from tour_guide.models.poi import POI
from tour_guide.services.narration_service import NarrationService
from tour_guide.services.poi_service import POIService

router = APIRouter()


def get_narration_service() -> NarrationService:
    raise NotImplementedError("NarrationService dependency not wired")


def get_personas() -> dict[str, PersonaConfig]:
    raise NotImplementedError("personas dependency not wired")


def get_poi_service() -> POIService:
    raise NotImplementedError("POIService dependency not wired")


class NarrationRequest(BaseModel):
    poi: POI
    persona: str
    lang: LangCode = "zh-TW"
    length: NarrationLength = "medium"
    force_regenerate: bool = False


@router.post("/narration")
async def narration(
    req: NarrationRequest,
    svc: Annotated[NarrationService, Depends(get_narration_service)] = None,
    personas: Annotated[dict[str, PersonaConfig], Depends(get_personas)] = None,
    poi_svc: Annotated[POIService, Depends(get_poi_service)] = None,
):
    persona = personas.get(req.persona)
    if persona is None:
        raise HTTPException(status_code=400, detail=f"Unknown persona: {req.persona}")

    poi_ctx = await poi_svc.context(req.poi)

    async def event_stream():
        async for ev in svc.narrate(
            persona=persona, poi_ctx=poi_ctx, lang=req.lang, length=req.length
        ):
            # sse-starlette accepts dicts: {"event": ..., "data": ...}
            import json
            yield {"event": ev.type, "data": json.dumps(ev.data, ensure_ascii=False)}

    return EventSourceResponse(event_stream())
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/integration/test_narration_api.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/api/narration.py backend/tests/integration/test_narration_api.py
git commit -m "feat(api): POST /narration SSE endpoint (fake-provider tested)"
```

---

### Task 21: POICache (filesystem LRU + TTL)

**Files:**
- Create: `backend/src/tour_guide/cache/__init__.py`
- Create: `backend/src/tour_guide/cache/poi_cache.py`
- Create: `backend/tests/unit/test_poi_cache.py`

- [ ] **Step 1: Write the failing test**

```python
import time
from pathlib import Path

import pytest
from freezegun import freeze_time

from tour_guide.cache.poi_cache import POICache


def test_put_then_get_returns_value(tmp_path: Path):
    c = POICache(tmp_path, ttl_s=60)
    c.put("k1", b"hello")
    assert c.get("k1") == b"hello"


def test_get_returns_none_for_missing(tmp_path: Path):
    c = POICache(tmp_path, ttl_s=60)
    assert c.get("missing") is None


def test_ttl_expired_returns_none(tmp_path: Path):
    with freeze_time("2026-05-08 12:00:00") as frozen:
        c = POICache(tmp_path, ttl_s=60)
        c.put("k1", b"x")
        frozen.tick(delta=61)
        assert c.get("k1") is None


def test_invalidate_removes_key(tmp_path: Path):
    c = POICache(tmp_path, ttl_s=60)
    c.put("k1", b"x")
    c.invalidate("k1")
    assert c.get("k1") is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_poi_cache.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/cache/__init__.py`**

```python
```
(empty)

- [ ] **Step 4: Create `backend/src/tour_guide/cache/poi_cache.py`**

```python
"""Filesystem POI cache with TTL. Single-process, no locking."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path


class POICache:
    """Stores bytes by string key, TTL-bounded. Files named by key hash."""

    def __init__(self, directory: Path, ttl_s: int = 30 * 24 * 3600) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl_s = ttl_s

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self._dir / f"{h}.bin"

    def get(self, key: str) -> bytes | None:
        p = self._path(key)
        if not p.exists():
            return None
        if time.time() - p.stat().st_mtime > self._ttl_s:
            p.unlink(missing_ok=True)
            return None
        return p.read_bytes()

    def put(self, key: str, value: bytes) -> None:
        self._path(key).write_bytes(value)

    def invalidate(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
```

- [ ] **Step 5: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_poi_cache.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/cache/ backend/tests/unit/test_poi_cache.py
git commit -m "feat(cache): POICache filesystem store with TTL"
```

---

### Task 22: NarrationCache (filesystem, stores audio + transcript)

**Files:**
- Create: `backend/src/tour_guide/cache/narration_cache.py`
- Create: `backend/tests/unit/test_narration_cache.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from tour_guide.cache.narration_cache import NarrationCache, CachedNarration


def test_put_then_get(tmp_path: Path):
    c = NarrationCache(tmp_path)
    cached = CachedNarration(audio_bytes=b"AUDIO", transcript="hello world", sentences=2)
    c.put(poi_id="osm:way:1", persona="history_uncle", lang="zh-TW", length="medium", value=cached)

    got = c.get(poi_id="osm:way:1", persona="history_uncle", lang="zh-TW", length="medium")
    assert got == cached


def test_get_misses_with_different_key(tmp_path: Path):
    c = NarrationCache(tmp_path)
    c.put(poi_id="osm:way:1", persona="history_uncle", lang="zh-TW", length="medium",
          value=CachedNarration(audio_bytes=b"x", transcript="x", sentences=1))
    assert c.get(poi_id="osm:way:1", persona="story_brother", lang="zh-TW", length="medium") is None
    assert c.get(poi_id="osm:way:1", persona="history_uncle", lang="en", length="medium") is None
    assert c.get(poi_id="osm:way:1", persona="history_uncle", lang="zh-TW", length="long") is None


def test_invalidate(tmp_path: Path):
    c = NarrationCache(tmp_path)
    c.put(poi_id="osm:way:1", persona="history_uncle", lang="zh-TW", length="medium",
          value=CachedNarration(audio_bytes=b"x", transcript="x", sentences=1))
    c.invalidate(poi_id="osm:way:1", persona="history_uncle", lang="zh-TW", length="medium")
    assert c.get(poi_id="osm:way:1", persona="history_uncle", lang="zh-TW", length="medium") is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_narration_cache.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/cache/narration_cache.py`**

```python
"""Filesystem cache for fully-rendered narrations (audio bytes + transcript)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CachedNarration:
    audio_bytes: bytes
    transcript: str
    sentences: int


class NarrationCache:
    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(poi_id: str, persona: str, lang: str, length: str) -> str:
        return f"{poi_id}|{persona}|{lang}|{length}"

    def _paths(self, poi_id: str, persona: str, lang: str, length: str) -> tuple[Path, Path]:
        h = hashlib.sha256(self._key(poi_id, persona, lang, length).encode("utf-8")).hexdigest()[:32]
        return self._dir / f"{h}.audio", self._dir / f"{h}.meta.json"

    def get(self, *, poi_id: str, persona: str, lang: str, length: str) -> CachedNarration | None:
        audio_p, meta_p = self._paths(poi_id, persona, lang, length)
        if not audio_p.exists() or not meta_p.exists():
            return None
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        return CachedNarration(
            audio_bytes=audio_p.read_bytes(),
            transcript=meta["transcript"],
            sentences=meta["sentences"],
        )

    def put(self, *, poi_id: str, persona: str, lang: str, length: str, value: CachedNarration) -> None:
        audio_p, meta_p = self._paths(poi_id, persona, lang, length)
        audio_p.write_bytes(value.audio_bytes)
        meta_p.write_text(
            json.dumps({"transcript": value.transcript, "sentences": value.sentences}),
            encoding="utf-8",
        )

    def invalidate(self, *, poi_id: str, persona: str, lang: str, length: str) -> None:
        for p in self._paths(poi_id, persona, lang, length):
            p.unlink(missing_ok=True)
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_narration_cache.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/cache/narration_cache.py backend/tests/unit/test_narration_cache.py
git commit -m "feat(cache): NarrationCache filesystem store"
```

---

### Task 23: Wire NarrationCache into NarrationService

**Files:**
- Modify: `backend/src/tour_guide/services/narration_service.py`
- Modify: `backend/tests/unit/test_narration_service.py`

- [ ] **Step 1: Write the new failing test (append)**

```python
@pytest.mark.asyncio
async def test_cache_hit_yields_audio_without_calling_llm():
    from tour_guide.cache.narration_cache import NarrationCache, CachedNarration

    llm = FakeLlmProvider([])  # would fail if called (no chunks)
    tts = FakeTtsProvider()

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        cache = NarrationCache(Path(td))
        cache.put(
            poi_id="osm:way:1", persona="history_uncle", lang="zh-TW", length="medium",
            value=CachedNarration(audio_bytes=b"CACHED", transcript="cached transcript", sentences=3),
        )
        svc = NarrationService(
            llm=llm, tts=tts, prompt_builder=PromptBuilder(),
            llm_model="x", cache=cache,
        )

        events = [e async for e in svc.narrate(
            persona=_persona(), poi_ctx=_poi_ctx(), lang="zh-TW", length="medium"
        )]

    types = [e.type for e in events]
    assert types[0] == "meta"
    assert events[0].data["cache_hit"] is True
    assert "audio" in types
    assert types[-1] == "end"
    assert llm.calls == []   # never called


@pytest.mark.asyncio
async def test_force_regenerate_bypasses_cache():
    from tour_guide.cache.narration_cache import NarrationCache, CachedNarration
    import tempfile
    from pathlib import Path

    llm = FakeLlmProvider(["新內容。"])
    tts = FakeTtsProvider()
    with tempfile.TemporaryDirectory() as td:
        cache = NarrationCache(Path(td))
        cache.put(
            poi_id="osm:way:1", persona="history_uncle", lang="zh-TW", length="medium",
            value=CachedNarration(audio_bytes=b"OLD", transcript="old", sentences=1),
        )
        svc = NarrationService(
            llm=llm, tts=tts, prompt_builder=PromptBuilder(),
            llm_model="x", cache=cache,
        )

        events = [e async for e in svc.narrate(
            persona=_persona(), poi_ctx=_poi_ctx(), lang="zh-TW",
            length="medium", force_regenerate=True,
        )]

    assert events[0].data["cache_hit"] is False
    assert llm.calls != []
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/unit/test_narration_service.py -v
```
Expected: TypeError on missing `cache=` param or missing `force_regenerate` param.

- [ ] **Step 3: Modify `backend/src/tour_guide/services/narration_service.py`**

Replace the `__init__` and `narrate` body:

```python
"""NarrationService — orchestrates the streaming narration pipeline."""
from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from tour_guide.cache.narration_cache import CachedNarration, NarrationCache
from tour_guide.models.persona import LangCode, NarrationLength, PersonaConfig
from tour_guide.models.poi import POIContext
from tour_guide.pipeline.sentence_splitter import StreamingSentenceBuffer
from tour_guide.prompts.builder import PromptBuilder
from tour_guide.providers.llm import LlmProvider
from tour_guide.providers.tts import TtsProvider


@dataclass
class NarrationEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


class NarrationService:
    def __init__(
        self,
        *,
        llm: LlmProvider,
        tts: TtsProvider,
        prompt_builder: PromptBuilder,
        llm_model: str,
        cache: NarrationCache | None = None,
    ) -> None:
        self._llm = llm
        self._tts = tts
        self._prompt_builder = prompt_builder
        self._llm_model = llm_model
        self._cache = cache

    async def narrate(
        self,
        *,
        persona: PersonaConfig,
        poi_ctx: POIContext,
        lang: LangCode,
        length: NarrationLength,
        force_regenerate: bool = False,
    ) -> AsyncIterator[NarrationEvent]:
        cache_hit = False
        cached: CachedNarration | None = None
        if self._cache is not None and not force_regenerate:
            cached = self._cache.get(
                poi_id=poi_ctx.poi.id, persona=persona.id, lang=lang, length=length,
            )
            cache_hit = cached is not None

        yield NarrationEvent(type="meta", data={
            "poi_id": poi_ctx.poi.id,
            "confidence": poi_ctx.confidence,
            "persona": persona.id,
            "lang": lang,
            "cache_hit": cache_hit,
        })

        if cached is not None:
            yield NarrationEvent(type="text", data={"chunk": cached.transcript})
            yield NarrationEvent(type="audio", data={
                "chunk_b64": _b64(cached.audio_bytes), "sentence_idx": 0,
            })
            yield NarrationEvent(type="end", data={"sentences": cached.sentences})
            return

        # Streaming path
        messages = self._prompt_builder.build_narration(
            persona=persona, poi_ctx=poi_ctx, lang=lang, length=length
        )
        voice_id = persona.voice[lang]
        buf = StreamingSentenceBuffer()
        sentence_idx = 0
        full_text_parts: list[str] = []
        full_audio_parts: list[bytes] = []

        async for text_chunk in self._llm.chat_stream(
            messages=messages, model=self._llm_model
        ):
            full_text_parts.append(text_chunk)
            yield NarrationEvent(type="text", data={"chunk": text_chunk})
            for sentence in buf.feed(text_chunk):
                async for audio in self._tts.synthesize(
                    text=sentence, voice_id=voice_id,
                    speaking_rate=persona.voice_style.speaking_rate,
                    emotion=persona.voice_style.emotion,
                ):
                    full_audio_parts.append(audio)
                    yield NarrationEvent(type="audio", data={
                        "chunk_b64": _b64(audio), "sentence_idx": sentence_idx,
                    })
                sentence_idx += 1

        for sentence in buf.flush():
            async for audio in self._tts.synthesize(
                text=sentence, voice_id=voice_id,
                speaking_rate=persona.voice_style.speaking_rate,
                emotion=persona.voice_style.emotion,
            ):
                full_audio_parts.append(audio)
                yield NarrationEvent(type="audio", data={
                    "chunk_b64": _b64(audio), "sentence_idx": sentence_idx,
                })
            sentence_idx += 1

        if self._cache is not None:
            self._cache.put(
                poi_id=poi_ctx.poi.id, persona=persona.id, lang=lang, length=length,
                value=CachedNarration(
                    audio_bytes=b"".join(full_audio_parts),
                    transcript="".join(full_text_parts),
                    sentences=sentence_idx,
                ),
            )

        yield NarrationEvent(type="end", data={"sentences": sentence_idx})
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/unit/test_narration_service.py -v
```
Expected: all (4) passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/narration_service.py backend/tests/unit/test_narration_service.py
git commit -m "feat(services): NarrationCache integration + force_regenerate flag"
```

---

### Task 24: LiteLLM Gemini adapter (real LLM)

**Files:**
- Modify: `backend/src/tour_guide/providers/llm.py`

- [ ] **Step 1: Append `LiteLLMProvider` to `backend/src/tour_guide/providers/llm.py`**

```python
class LiteLLMProvider:
    """Real LLM provider via LiteLLM (supports Gemini, Claude, OpenAI, ...)."""

    def __init__(self, *, api_key: str) -> None:
        # LiteLLM reads the key from env per-provider; we set it here for Gemini.
        import os
        os.environ.setdefault("GEMINI_API_KEY", api_key)

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        import litellm
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
```

- [ ] **Step 2: Verify import (no automated test — exercised in Task 28 smoke)**

```bash
cd backend && python -c "from tour_guide.providers.llm import LiteLLMProvider; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/tour_guide/providers/llm.py
git commit -m "feat(providers): LiteLLMProvider real LLM adapter"
```

---

### Task 25: Gemini TTS adapter (real TTS)

**Files:**
- Modify: `backend/src/tour_guide/providers/tts.py`

- [ ] **Step 1: Append `GeminiTtsProvider` to `backend/src/tour_guide/providers/tts.py`**

```python
class GeminiTtsProvider:
    """Real TTS via Google GenAI SDK using Gemini 2.5 Flash Preview TTS."""

    def __init__(self, *, api_key: str, model: str = "gemini-2.5-flash-preview-tts") -> None:
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        speaking_rate: float = 1.0,
        emotion: str | None = None,
    ):
        from google.genai import types

        # google-genai is sync; wrap each call in to_thread.
        import asyncio

        def _call() -> bytes:
            response = self._client.models.generate_content(
                model=self._model,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_id,
                            ),
                        ),
                    ),
                ),
            )
            # Extract inline audio bytes (PCM in WAV-ready container per SDK)
            for cand in response.candidates or []:
                for part in cand.content.parts or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and inline.data:
                        return inline.data
            return b""

        audio = await asyncio.to_thread(_call)
        if audio:
            yield audio
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from tour_guide.providers.tts import GeminiTtsProvider; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/tour_guide/providers/tts.py
git commit -m "feat(providers): GeminiTtsProvider real TTS adapter"
```

---

### Task 26: FastAPI app factory + DI wiring

**Files:**
- Create: `backend/src/tour_guide/main.py`
- Create: `backend/tests/integration/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from tour_guide.main import create_app


def test_app_has_health_endpoint(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    app = create_app()
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200


def test_app_routes_include_narration_and_poi(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/poi/nearby" in paths
    assert "/narration" in paths
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/integration/test_main.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `backend/src/tour_guide/main.py`**

```python
"""FastAPI app factory + dependency wiring."""
from __future__ import annotations

import httpx
from fastapi import FastAPI

from tour_guide.api import health, narration, poi
from tour_guide.cache.narration_cache import NarrationCache
from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.overpass import OverpassClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.config import AppConfig
from tour_guide.prompts.builder import PromptBuilder
from tour_guide.prompts.loader import load_all_personas
from tour_guide.providers.llm import LiteLLMProvider
from tour_guide.providers.tts import GeminiTtsProvider
from tour_guide.services.narration_service import NarrationService
from tour_guide.services.poi_service import POIService


def create_app() -> FastAPI:
    cfg = AppConfig()
    app = FastAPI(title="AI Tour Guide Backend", version="0.1.0")

    # Singletons
    http_client = httpx.AsyncClient()
    overpass = OverpassClient(http_client)
    wikipedia = WikipediaClient(http_client)
    poi_cache = POICache(cfg.poi_cache_dir)
    narration_cache = NarrationCache(cfg.narration_cache_dir)

    poi_service = POIService(overpass=overpass, wikipedia=wikipedia)
    llm = LiteLLMProvider(api_key=cfg.gemini_api_key)
    tts = GeminiTtsProvider(api_key=cfg.gemini_api_key, model=cfg.tts_model)
    narration_service = NarrationService(
        llm=llm, tts=tts, prompt_builder=PromptBuilder(),
        llm_model=cfg.llm_model, cache=narration_cache,
    )
    personas = load_all_personas(cfg.persona_dir)

    # Routers
    app.include_router(health.router)
    app.include_router(poi.router)
    app.include_router(narration.router)

    # DI overrides
    app.dependency_overrides[poi.get_poi_service] = lambda: poi_service
    app.dependency_overrides[narration.get_narration_service] = lambda: narration_service
    app.dependency_overrides[narration.get_personas] = lambda: personas
    app.dependency_overrides[narration.get_poi_service] = lambda: poi_service

    @app.on_event("shutdown")
    async def _close_http():
        await http_client.aclose()

    return app


app = create_app()
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && pytest tests/integration/test_main.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Manual server smoke**

```bash
cd backend && GEMINI_API_KEY=anything-fake-for-import uvicorn tour_guide.main:app --port 8000 --reload &
sleep 2
curl -s http://localhost:8000/health
kill %1
```
Expected: `{"status":"ok","uptime_s":...}`. Then process killed cleanly.

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/main.py backend/tests/integration/test_main.py
git commit -m "feat(app): FastAPI factory + dependency wiring"
```

---

### Task 27: Run all tests + ruff lint

**Files:**
- (none — verification step)

- [ ] **Step 1: Run all tests**

```bash
cd backend && pytest -v
```
Expected: all tests pass (~40+ tests across 12 test files).

- [ ] **Step 2: Run ruff**

```bash
cd backend && ruff check src/ tests/
```
Expected: no errors. Fix any reported issues inline (most likely import ordering — `ruff check --fix src/ tests/`).

- [ ] **Step 3: Run ruff format check**

```bash
cd backend && ruff format --check src/ tests/
```
Expected: clean. If not, run `ruff format src/ tests/` then re-check.

- [ ] **Step 4: Commit any formatting fixes**

```bash
git add -u
git diff --cached --quiet || git commit -m "style: ruff format"
```

---

### Task 28: Real-provider smoke test (gated, manual run)

**Files:**
- Create: `backend/tests/smoke/test_real_providers.py`

- [ ] **Step 1: Create `backend/tests/smoke/test_real_providers.py`**

```python
"""Real-provider smoke tests. Run with `pytest -m real_provider`. Costs $."""
import os

import pytest

from tour_guide.providers.llm import LiteLLMProvider
from tour_guide.providers.tts import GeminiTtsProvider


pytestmark = pytest.mark.real_provider


@pytest.fixture
def api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key or key == "fake":
        pytest.skip("GEMINI_API_KEY not set with a real value")
    return key


@pytest.mark.asyncio
async def test_litellm_gemini_streams_text(api_key: str):
    p = LiteLLMProvider(api_key=api_key)
    chunks = []
    async for c in p.chat_stream(
        messages=[{"role": "user", "content": "用一句話說台北 101。"}],
        model="gemini/gemini-2.5-flash",
        max_tokens=100,
    ):
        chunks.append(c)
    full = "".join(chunks)
    assert len(full) > 0
    assert "101" in full or "Taipei" in full or "台北" in full


@pytest.mark.asyncio
async def test_gemini_tts_returns_audio(api_key: str):
    p = GeminiTtsProvider(api_key=api_key)
    audio_chunks = []
    async for chunk in p.synthesize(text="你好，世界。", voice_id="Charon"):
        audio_chunks.append(chunk)
    total = b"".join(audio_chunks)
    assert len(total) > 1000   # non-trivial audio bytes
```

- [ ] **Step 2: Verify default test run skips them**

```bash
cd backend && pytest -v
```
Expected: smoke tests show as `SKIPPED (test requires real_provider)`.

- [ ] **Step 3: Manual real-run (only if you want to verify against real Gemini)**

```bash
cd backend && GEMINI_API_KEY=<your-real-key> pytest -m real_provider -v
```
Expected: 2 passed (will cost ~$0.0005).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/smoke/test_real_providers.py
git commit -m "test(smoke): real-provider gated smoke tests for Gemini LLM + TTS"
```

---

### Task 29: README curl recipes + end-to-end manual recipe

**Files:**
- Modify: `backend/README.md`

- [ ] **Step 1: Append usage section to `backend/README.md`**

```markdown
## End-to-end manual test

Start the server:

```bash
cd backend
source .venv/bin/activate
GEMINI_API_KEY=<your-real-key> uvicorn tour_guide.main:app --reload
```

In another terminal:

### Health check

```bash
curl -s http://localhost:8000/health | jq
```

### Find nearby POIs

```bash
# Coordinates near 國立故宮博物院 (Taipei)
curl -s "http://localhost:8000/poi/nearby?lat=25.1023&lon=121.5482&radius=500&lang=zh-TW" | jq
```

### Stream a narration

```bash
curl -N -X POST http://localhost:8000/narration \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "poi": {
      "id": "osm:way:35243722",
      "name": "國立故宮博物院",
      "name_localized": "國立故宮博物院",
      "lat": 25.1023,
      "lon": 121.5482,
      "tags": {"tourism": "museum", "wikipedia": "zh:國立故宮博物院"}
    },
    "persona": "history_uncle",
    "lang": "zh-TW",
    "length": "short"
  }'
```

You should see a stream of `event: meta`, then alternating `event: text` and
`event: audio` blocks (the audio is base64-encoded mp3-ish PCM), ending with
`event: end`.

To save the streamed audio to a playable file, see the helper script in
`backend/scripts/curl_narration_to_wav.py` (Plan B will build this — for now
verify in terminal that events are flowing).
```

- [ ] **Step 2: Commit**

```bash
git add backend/README.md
git commit -m "docs(backend): curl recipes for /poi/nearby and /narration"
```

---

## Self-Review Checklist (run after writing this plan)

This was checked during plan authoring; no live action needed by the executor:

- **Spec coverage**:
  - Sec 4.2 backend modules → Tasks 5–22 cover POIService, NarrationService, providers, clients, prompts, cache, sentence_splitter, confidence
  - Sec 6.1 `/poi/nearby` → Task 19
  - Sec 6.2 `/narration` SSE → Tasks 17, 20, 23
  - Sec 6.4 `/health` → Task 18
  - Sec 7.2 backend cache → Tasks 21, 22
  - Sec 8 persona system → Tasks 5, 6, 7
  - Sec 10.2 testing → every task has TDD red/green; smoke gated in Task 28
  - **Out of scope per Plan A**: `/qa`, multi-persona, multi-lang beyond zh-TW, foodie, deployment, X-API-Key — explicitly listed at top

- **Type consistency**: `PersonaConfig` shape matches across `loader`, `builder`, `narration_service`. `NarrationEvent` defined once and imported. `POI`/`POIContext`/`WikiArticle` consistent across services. `LangCode` / `NarrationLength` are a single Literal each.

- **Placeholder scan**: every step shows actual code or actual command. No "TODO" / "TBD" / "appropriate".

---

## Plan A — Done Definition

By the end of Task 29 you should be able to:

1. `pytest` shows ~40+ green tests, no smoke tests run by default
2. `uvicorn tour_guide.main:app --reload` starts cleanly
3. `curl /health` returns 200
4. `curl /poi/nearby?lat=...&lon=...` returns real Taipei POIs from OSM with Wikipedia summaries
5. `curl -N -X POST /narration ...` streams `meta → text/audio* → end` SSE events with a real Gemini-narrated `history_uncle` voice in zh-TW
6. Repeating the same `/narration` call returns instantly (cache hit, `cache_hit: true` in meta)

This is the foundation Plan B (Flutter App MVP) will consume.
