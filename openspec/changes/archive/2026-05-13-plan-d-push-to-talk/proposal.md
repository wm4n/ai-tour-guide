## Why

目前 AI Tour Guide App 只能被動播放旁白，使用者無法主動向 AI 提問。加入 Push-to-talk Q&A 功能後，使用者可長按麥克風按鈕錄音，後端透過 STT → LLM → TTS 串流回答，顯著提升互動深度與使用者體驗。

## What Changes

- 新增 `POST /qa` SSE endpoint：接收音訊 + context，回傳 `transcript → text/audio → end` 事件流
- 新增 `SttProvider` abstraction（Protocol + `GeminiSttAdapter` + `FakeSttProvider`）
- 新增 `QAService`：STT → PromptBuilder.build_qa() → LLM → TTS pipeline
- 擴充 `PromptBuilder.build_qa()`：支援有/無 POI context 兩種 Q&A prompt 分支
- 新增 Flutter `MicRecorderService`（`record ^5.0` 套件），WAV 格式錄音
- 新增 Flutter `QaNotifier`（Riverpod StateNotifier）管理 Q&A 狀態機（idle/recording/processing/answering/error）
- 新增 Flutter `PushToTalkButton` widget，整合至 MapScreen 底部
- 擴充 `AudioPlayerService.duck() / unduck()`：Q&A 期間旁白音量降至 50%，Q&A 結束後恢復
- 新增 Flutter `qaAudioPlayerProvider`（獨立第二個 AudioPlayer 實例，播放 Q&A 音訊）
- 擴充 `BackendClient.qa()`：multipart/form-data POST + SSE 解析
- 擴充 `NarrationSheet`：在旁白字幕上方顯示 Q&A transcript 和回覆字幕

## Capabilities

### New Capabilities

- `push-to-talk-qa`: 長按錄音觸發 STT→LLM→TTS 問答流程，旁白 ducking，獨立 Q&A AudioPlayer

### Modified Capabilities

- `narration-stream`: `AudioPlayerService` 新增 `duck()` / `unduck()` 方法（介面變更，現有實作需更新）

## Impact

**Backend 新增：**
- `backend/src/tour_guide/providers/stt.py`
- `backend/src/tour_guide/services/qa_service.py`
- `backend/src/tour_guide/api/qa.py`
- `backend/src/tour_guide/prompts/builder.py`（新增 `build_qa()`）
- `backend/src/tour_guide/main.py`（wire QAService + qa router）

**Flutter 新增：**
- `flutter_app/lib/shared/mic/mic_recorder_service.dart`
- `flutter_app/lib/shared/backend/models/qa_event.dart`
- `flutter_app/lib/features/qa/providers/qa_provider.dart`
- `flutter_app/lib/features/qa/widgets/push_to_talk_button.dart`

**Flutter 修改：**
- `flutter_app/lib/shared/audio/audio_player_service.dart`（duck/unduck）
- `flutter_app/lib/shared/backend/backend_client.dart`（qa() 方法）
- `flutter_app/lib/shared/providers.dart`（新增 qaAudioPlayerProvider、micRecorderProvider）
- `flutter_app/lib/features/map/screens/map_screen.dart`（整合 PushToTalkButton）
- `flutter_app/lib/features/narration/widgets/narration_sheet.dart`（Q&A 字幕區塊）

**依賴新增：**
- Flutter：`record: ^5.0.0`
- Backend：無新增（Gemini STT 走現有 `google-genai` SDK）

**明確不在範圍：**
- VAD 自動停止錄音（Plan D 用 push-to-talk 明確邊界）
- 問答歷史記錄（LocalDB）
- Q&A 旁白字幕時間對齊
- 背景錄音
