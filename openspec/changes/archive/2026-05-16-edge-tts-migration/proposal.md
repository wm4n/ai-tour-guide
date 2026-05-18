## Why

Gemini TTS (`gemini-2.5-flash-preview-tts`) 免費配額嚴重不足，開發測試期間頻繁觸發 429 rate limit，阻礙日常開發流程。Microsoft Edge TTS（`edge-tts` Python package）提供完全免費、無配額限制的 Neural 品質語音合成，且原生支援 zh-TW 語音，是當前最佳替代方案。

## What Changes

- **新增** `edge-tts>=7.0.0` Python dependency 至 `backend/pyproject.toml`
- **新增** `EdgeTtsAdapter` class 至 `backend/src/tour_guide/providers/tts.py`，實作現有 `TtsProvider` Protocol
- **移除** Gemini TTS wiring，改為 `EdgeTtsAdapter` 作為預設 TTS provider
- **更新** 5 個 persona YAML 的 voice mapping，從 Gemini voice ID 換成 Edge TTS voice ID（zh-TW/en 各一）
- **更新** Flutter `AudioPlayerService`：audio chunk 副檔名從 `.wav` 改為 `.mp3`（Edge TTS 輸出格式）
- **新增** `backend/tests/unit/test_edge_tts_adapter.py` 單元測試

## Capabilities

### New Capabilities

<!-- 此次異動不引入新的 spec-level capability，僅是現有 narration-stream 能力的 implementation 替換 -->

### Modified Capabilities

- `narration-stream`: audio chunk 格式從 WAV 變更為 MP3；TTS provider 由 Gemini 換為 Edge TTS，voice ID 格式改變（如 `zh-TW-YunJheNeural`）

## Impact

- **Backend**: `backend/pyproject.toml`（新增 dependency）、`backend/src/tour_guide/providers/tts.py`（新增 adapter）、`backend/src/tour_guide/main.py`（更換 wiring）、`backend/data/personas/*.yaml`（5 個 voice mapping）
- **Backend Tests**: 新增 `backend/tests/unit/test_edge_tts_adapter.py`
- **Flutter**: `flutter_app/lib/shared/audio/audio_player_service.dart`（`.wav` → `.mp3`）
- **無 API 異動**：`POST /narration` SSE 協議不變，前後端合約不受影響
- **無環境變數異動**：Edge TTS 不需要 API key，移除 Gemini TTS key 依賴
