# Edge TTS Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 backend TTS 引擎從 Gemini TTS 換成 Microsoft Edge TTS（`edge-tts`），解除 Gemini 免費配額限制。

**Architecture:** 在 `providers/tts.py` 新增 `EdgeTtsAdapter`，實作現有 `TtsProvider` Protocol，輸出 MP3 串流。在 `main.py` 換掉一行 wiring。更新 persona YAML voice ID 為 edge-tts 格式。Flutter 端將暫存檔副檔名從 `.wav` 改為 `.mp3`。

**Tech Stack:** `edge-tts>=7.0.0`（Python async TTS client），`pytest-asyncio`（現有測試框架），`just_audio`（Flutter 音訊播放，已存在）

---

## File Map

| 動作 | 檔案 |
|------|------|
| Modify | `backend/pyproject.toml` |
| Modify | `backend/src/tour_guide/providers/tts.py` |
| Modify | `backend/src/tour_guide/main.py` |
| Modify | `backend/prompts/personas/history_uncle.yaml` |
| Modify | `backend/prompts/personas/story_brother.yaml` |
| Modify | `backend/prompts/personas/kid_sister.yaml` |
| Modify | `backend/prompts/personas/gossip_auntie.yaml` |
| Modify | `backend/prompts/personas/foodie.yaml` |
| Modify | `flutter_app/lib/shared/audio/audio_player_service.dart` |
| Create | `backend/tests/unit/test_edge_tts_adapter.py` |

---

### Task 1：安裝 `edge-tts` 依賴

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 在 `pyproject.toml` 新增依賴**

在 `dependencies` 列表加入 `edge-tts`：

```toml
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
    "python-multipart>=0.0.9",
    "edge-tts>=7.0.0",
]
```

- [ ] **Step 2: 安裝依賴**

```bash
cd backend
pip install -e ".[dev]"
```

Expected: 安裝成功，輸出包含 `Successfully installed edge-tts-7.x.x`（或已是最新版）

- [ ] **Step 3: 驗證 import 正常**

```bash
python -c "import edge_tts; print('ok')"
```

Expected: 印出 `ok`，無 ImportError

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "feat(backend): add edge-tts dependency"
```

---

### Task 2：實作 `EdgeTtsAdapter`（TDD）

**Files:**
- Modify: `backend/src/tour_guide/providers/tts.py`
- Create: `backend/tests/unit/test_edge_tts_adapter.py`

- [ ] **Step 1: 寫失敗測試**

建立 `backend/tests/unit/test_edge_tts_adapter.py`：

```python
from unittest.mock import MagicMock, patch

import pytest

from tour_guide.providers.tts import EdgeTtsAdapter, TtsOpts


@pytest.mark.asyncio
async def test_edge_tts_adapter_yields_audio_chunks():
    """EdgeTtsAdapter yields bytes from edge_tts audio chunks."""
    raw = [
        {"type": "audio", "data": b"chunk1"},
        {"type": "WordBoundary"},
        {"type": "audio", "data": b"chunk2"},
    ]

    async def mock_stream():
        for chunk in raw:
            yield chunk

    mock_communicate = MagicMock()
    mock_communicate.stream = mock_stream

    with patch("tour_guide.providers.tts.edge_tts.Communicate", return_value=mock_communicate):
        adapter = EdgeTtsAdapter()
        chunks = []
        async for chunk in adapter.synthesize("hello", "zh-TW-YunJheNeural", TtsOpts()):
            chunks.append(chunk)

    assert chunks == [b"chunk1", b"chunk2"]


@pytest.mark.asyncio
async def test_edge_tts_adapter_skips_non_audio_chunks():
    """EdgeTtsAdapter ignores chunks that are not type 'audio'."""
    raw = [
        {"type": "WordBoundary"},
        {"type": "SessionEnd"},
    ]

    async def mock_stream():
        for chunk in raw:
            yield chunk

    mock_communicate = MagicMock()
    mock_communicate.stream = mock_stream

    with patch("tour_guide.providers.tts.edge_tts.Communicate", return_value=mock_communicate):
        adapter = EdgeTtsAdapter()
        chunks = []
        async for chunk in adapter.synthesize("hello", "en-US-GuyNeural", TtsOpts()):
            chunks.append(chunk)

    assert chunks == []
```

- [ ] **Step 2: 執行測試，確認失敗**

```bash
cd backend
python -m pytest tests/unit/test_edge_tts_adapter.py -v
```

Expected: `ImportError: cannot import name 'EdgeTtsAdapter'`

- [ ] **Step 3: 在 `tts.py` 實作 `EdgeTtsAdapter`**

在 `backend/src/tour_guide/providers/tts.py` 頂部加入 import，並在檔案末尾（`GeminiTtsAdapter` 之後）新增：

頂部加入（與其他 import 一起）：
```python
import edge_tts
```

檔案末尾新增：
```python
class EdgeTtsAdapter:
    """TTS provider using Microsoft Edge TTS (free, no API key required)."""

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        opts: TtsOpts,
    ) -> AsyncIterator[bytes]:
        communicate = edge_tts.Communicate(text, voice_id)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
```

- [ ] **Step 4: 執行測試，確認通過**

```bash
cd backend
python -m pytest tests/unit/test_edge_tts_adapter.py -v
```

Expected:
```
PASSED tests/unit/test_edge_tts_adapter.py::test_edge_tts_adapter_yields_audio_chunks
PASSED tests/unit/test_edge_tts_adapter.py::test_edge_tts_adapter_skips_non_audio_chunks
```

- [ ] **Step 5: 執行完整 unit test suite，確認無 regression**

```bash
cd backend
python -m pytest tests/unit/ -v
```

Expected: 全部 PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/providers/tts.py \
        backend/tests/unit/test_edge_tts_adapter.py
git commit -m "feat(backend): add EdgeTtsAdapter using edge-tts"
```

---

### Task 3：更新 `main.py` wiring

**Files:**
- Modify: `backend/src/tour_guide/main.py`

- [ ] **Step 1: 替換 import 與 wiring**

在 `backend/src/tour_guide/main.py` 中：

1. 將 import 行：
```python
from tour_guide.providers.tts import GeminiTtsAdapter
```
改為：
```python
from tour_guide.providers.tts import EdgeTtsAdapter
```

2. 將 wiring 行：
```python
tts_provider = GeminiTtsAdapter(api_key=config.gemini_api_key)
```
改為：
```python
tts_provider = EdgeTtsAdapter()
```

- [ ] **Step 2: 確認 app 能啟動**

```bash
cd backend
python -c "from tour_guide.main import create_app; from tour_guide.config import AppConfig; app = create_app(AppConfig()); print('ok')"
```

Expected: 印出 `ok`，無 ImportError 或 TypeError

- [ ] **Step 3: Commit**

```bash
git add backend/src/tour_guide/main.py
git commit -m "feat(backend): wire EdgeTtsAdapter in app factory"
```

---

### Task 4：更新 Persona YAML voice ID

**Files:**
- Modify: `backend/prompts/personas/history_uncle.yaml`
- Modify: `backend/prompts/personas/story_brother.yaml`
- Modify: `backend/prompts/personas/kid_sister.yaml`
- Modify: `backend/prompts/personas/gossip_auntie.yaml`
- Modify: `backend/prompts/personas/foodie.yaml`

Voice mapping：

| Persona | zh-TW | en |
|---------|-------|----|
| history_uncle | `zh-TW-YunJheNeural` | `en-US-GuyNeural` |
| story_brother | `zh-TW-YunJheNeural` | `en-US-TonyNeural` |
| kid_sister | `zh-TW-HsiaoYuNeural` | `en-US-JennyNeural` |
| gossip_auntie | `zh-TW-HsiaoChenNeural` | `en-US-AriaNeural` |
| foodie | `zh-TW-HsiaoChenNeural` | `en-US-AriaNeural` |

- [ ] **Step 1: 更新 `history_uncle.yaml`**

將 `voice:` 區塊改為：
```yaml
voice:
  zh-TW: zh-TW-YunJheNeural
  en: en-US-GuyNeural
```

- [ ] **Step 2: 更新 `story_brother.yaml`**

將 `voice:` 區塊改為：
```yaml
voice:
  zh-TW: zh-TW-YunJheNeural
  en: en-US-TonyNeural
```

- [ ] **Step 3: 更新 `kid_sister.yaml`**

將 `voice:` 區塊改為：
```yaml
voice:
  zh-TW: zh-TW-HsiaoYuNeural
  en: en-US-JennyNeural
```

- [ ] **Step 4: 更新 `gossip_auntie.yaml`**

將 `voice:` 區塊改為：
```yaml
voice:
  zh-TW: zh-TW-HsiaoChenNeural
  en: en-US-AriaNeural
```

- [ ] **Step 5: 更新 `foodie.yaml`**

將 `voice:` 區塊改為：
```yaml
voice:
  zh-TW: zh-TW-HsiaoChenNeural
  en: en-US-AriaNeural
```

- [ ] **Step 6: 驗證 persona 載入正常**

```bash
cd backend
python -c "
from tour_guide.prompts.loader import PersonaLoader
registry = PersonaLoader.load_all()
for pid, p in registry.items():
    print(pid, p.voice)
"
```

Expected：印出 5 個 persona，voice 值皆為 edge-tts 格式（如 `zh-TW-YunJheNeural`）

- [ ] **Step 7: Commit**

```bash
git add backend/prompts/personas/
git commit -m "feat(backend): update persona voice IDs to edge-tts format"
```

---

### Task 5：Flutter 音訊檔副檔名 `.wav` → `.mp3`

**Files:**
- Modify: `flutter_app/lib/shared/audio/audio_player_service.dart:37`

- [ ] **Step 1: 修改暫存檔副檔名**

將 `flutter_app/lib/shared/audio/audio_player_service.dart` 第 37 行：
```dart
final file = File('${_tempDir.path}/narration_${_chunkIndex++}.wav');
```
改為：
```dart
final file = File('${_tempDir.path}/narration_${_chunkIndex++}.mp3');
```

同步更新 `dispose()` 方法中第 84-87 行的清除邏輯（檔名 pattern 也要對應）：
```dart
for (var i = 0; i < _chunkIndex; i++) {
  final f = File('${_tempDir.path}/narration_$i.mp3');
  if (await f.exists()) await f.delete();
}
```

- [ ] **Step 2: Commit**

```bash
git add flutter_app/lib/shared/audio/audio_player_service.dart
git commit -m "feat(flutter): rename audio temp files to .mp3 to match edge-tts output"
```

---

### Task 6：端對端手動驗證

- [ ] **Step 1: 啟動 backend**

```bash
cd backend
uvicorn tour_guide.main:app --reload
```

Expected: 啟動成功，無 ImportError

- [ ] **Step 2: 呼叫 narration API，確認音訊回傳**

```bash
curl -N -H "Content-Type: application/json" \
  -d '{"poi_id":"test","persona_id":"history_uncle","lang":"zh-TW","length":"short"}' \
  http://localhost:8000/narration/stream
```

Expected: SSE stream 中出現 `event: audio` 事件，`data` 欄位含 base64 字串

- [ ] **Step 3: 在 Flutter app 實機測試**

啟動 Flutter app，走到任一 POI，確認：
1. 旁白文字正常出現
2. 音訊正常播放（男聲 zh-TW-YunJheNeural for history_uncle）
3. 無 crash 或 error log

- [ ] **Step 4: 執行完整 backend test suite**

```bash
cd backend
python -m pytest tests/unit/ -v
```

Expected: 全部 PASSED
