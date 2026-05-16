## 1. Backend Dependency

- [x] 1.1 在 `backend/pyproject.toml` dependencies 陣列新增 `"edge-tts>=7.0.0"`
- [x] 1.2 執行 `uv lock` 更新 lock file（或對應 lock 指令），確認 `edge-tts` 被 resolved

## 2. EdgeTtsAdapter 實作

- [x] 2.1 在 `backend/src/tour_guide/providers/tts.py` 新增 `import edge_tts`
- [x] 2.2 新增 `EdgeTtsAdapter` class，實作 `synthesize()` async generator：讀取 `communicate.stream()` 並 yield `chunk["data"]`（type == "audio"）

## 3. Wiring 更換

- [x] 3.1 在 `backend/src/tour_guide/main.py` 將 import 從 `GeminiTtsAdapter` 改為 `EdgeTtsAdapter`
- [x] 3.2 將 `tts_provider = GeminiTtsAdapter(api_key=config.gemini_api_key)` 改為 `tts_provider = EdgeTtsAdapter()`

## 4. Persona YAML Voice Mapping 更新

- [x] 4.1 更新 `backend/prompts/personas/history_uncle.yaml`：`voice.zh-TW: zh-TW-YunJheNeural`、`voice.en: en-US-GuyNeural`
- [x] 4.2 更新 `backend/prompts/personas/story_brother.yaml`：`voice.zh-TW: zh-TW-YunJheNeural`、`voice.en: en-US-TonyNeural`
- [x] 4.3 更新 `backend/prompts/personas/kid_sister.yaml`：`voice.zh-TW: zh-TW-HsiaoYuNeural`、`voice.en: en-US-JennyNeural`
- [x] 4.4 更新 `backend/prompts/personas/gossip_auntie.yaml`：`voice.zh-TW: zh-TW-HsiaoChenNeural`、`voice.en: en-US-AriaNeural`
- [x] 4.5 更新 `backend/prompts/personas/foodie.yaml`：`voice.zh-TW: zh-TW-HsiaoChenNeural`、`voice.en: en-US-AriaNeural`

## 5. Flutter Audio 格式更新

- [x] 5.1 在 `flutter_app/lib/shared/audio/audio_player_service.dart` 將 `enqueueBytes()` 中的 `narration_$i.wav` 改為 `narration_$i.mp3`
- [x] 5.2 在同檔案 `dispose()` 方法中，將清理邏輯的 `.wav` 改為 `.mp3`

## 6. 單元測試

- [x] 6.1 新建 `backend/tests/unit/test_edge_tts_adapter.py`，mock `edge_tts.Communicate` 的 `stream()` async generator
- [x] 6.2 測試：正常串流時，只有 `type == "audio"` 的 chunk data 被 yield
- [x] 6.3 測試：`type != "audio"`（如 `WordBoundary`）的 chunk 被過濾，不 yield
- [x] 6.4 執行 `pytest backend/tests/unit/test_edge_tts_adapter.py` 確認全部通過
