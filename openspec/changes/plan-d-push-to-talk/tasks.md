## 1. Backend — SttProvider

- [x] 1.1 建立 `backend/src/tour_guide/providers/stt.py`：定義 `SttProvider` Protocol、`FakeSttProvider`（scripted text）、`GeminiSttAdapter`（呼叫 Gemini multimodal API 轉錄 WAV bytes）
- [x] 1.2 在 `backend/src/tour_guide/providers/fakes.py` 末尾重新匯出 `FakeSttProvider`（from stt import）
- [x] 1.3 建立 `backend/tests/unit/test_stt_provider.py`，測試 FakeSttProvider 回傳 scripted text 和 default text
- [x] 1.4 執行 `pytest tests/unit/test_stt_provider.py -v` 確認 2 passed

## 2. Backend — PromptBuilder.build_qa()

- [x] 2.1 在 `backend/tests/unit/test_prompt_builder.py` 末尾新增 `TestPromptBuilderQA` class，涵蓋 with-poi、without-poi、english 三個測試案例（先確認 FAIL）
- [x] 2.2 在 `backend/src/tour_guide/prompts/builder.py` 的 `PromptBuilder` class 新增 `build_qa()` static method：有 POI context 時用 qa_template 填入 poi_name/narration_summary/user_question，無 POI 時用通用問答 prompt
- [x] 2.3 執行 `pytest tests/unit/test_prompt_builder.py -v` 確認全部通過

## 3. Backend — QAService（TDD）

- [x] 3.1 建立 `backend/tests/unit/test_qa_service.py`，測試：第一個 event 是 TranscriptEvent、最後一個 event 是 EndEvent、有 AudioEvent 出現（先確認 FAIL）
- [x] 3.2 建立 `backend/src/tour_guide/services/qa_service.py`：實作 `QAService.answer()` async generator — 呼叫 SttProvider → yield TranscriptEvent → build_qa messages → LLM stream → StreamingSentenceBuffer → yield TextEvent+AudioEvent per sentence → yield EndEvent；定義 TranscriptEvent / TextEvent / AudioEvent / EndEvent / ErrorEvent dataclasses
- [x] 3.3 執行 `pytest tests/unit/test_qa_service.py -v` 確認 3 passed

## 4. Backend — /qa Endpoint + Integration Test

- [x] 4.1 建立 `backend/tests/integration/test_qa_api.py`：使用 TestClient + FakeSttProvider + FakeLlmProvider + FakeTtsProvider，測試第一個 SSE event 是 transcript、最後是 end、audio event 有 chunk_b64、unknown persona 回 400、missing audio 回 422（先確認 FAIL）
- [x] 4.2 建立 `backend/src/tour_guide/api/qa.py`：定義 `get_qa_service` / `get_persona_registry` dependency stubs、`POST /qa` router — 讀取 multipart audio + context JSON、驗證 persona、呼叫 `qa_service.answer()`、StreamingResponse SSE 輸出
- [x] 4.3 執行 `pytest tests/integration/test_qa_api.py -v` 確認全部通過

## 5. Backend — Wire QAService in main.py

- [x] 5.1 更新 `backend/src/tour_guide/main.py`：import `GeminiSttAdapter` 和 `QAService`，在 `create_app()` 中建立 `stt_provider = GeminiSttAdapter(...)` 和 `qa_service = QAService(stt, llm, tts)`，覆寫 `qa.get_qa_service` 和 `qa.get_persona_registry` dependency，include `qa.router`
- [x] 5.2 執行 `pytest -v` 確認全部 backend 測試通過（0 failed）

## 6. Flutter — QaEvent sealed class

- [x] 6.1 建立 `flutter_app/lib/shared/backend/models/qa_event.dart`：定義 `QaEvent` sealed class 和子類別 `TranscriptQaEvent`、`TextQaEvent`、`AudioQaEvent`、`EndQaEvent`、`ErrorQaEvent`，每個子類別有對應的 `fromJson()` factory constructor
- [x] 6.2 在 `flutter_app/test/unit/models_test.dart` 末尾新增 `QaEvent` group，測試各子類別的 `fromJson()` 正確解析欄位
- [x] 6.3 執行 `flutter test test/unit/models_test.dart -v` 確認全部通過

## 7. Flutter — AudioPlayerService duck/unduck

- [x] 7.1 建立 `flutter_app/test/unit/audio_duck_test.dart`，測試 FakeAudioPlayerService 的 isDucked 初始為 false、duck() 後為 true、unduck() 後為 false（先確認 FAIL）
- [x] 7.2 更新 `flutter_app/lib/shared/audio/audio_player_service.dart`：在 `AudioPlayerService` abstract class 新增 `duck()` 和 `unduck()` 方法；`RealAudioPlayerService` 實作 `duck() → _player.setVolume(0.5)` 和 `unduck() → _player.setVolume(1.0)`；`FakeAudioPlayerService` 新增 `bool isDucked = false` 欄位並實作 duck/unduck
- [x] 7.3 執行 `flutter test test/unit/audio_duck_test.dart -v` 確認 3 passed
- [x] 7.4 執行 `flutter test -v` 確認所有既有測試仍通過

## 8. Flutter — MicRecorderService + record 套件

- [x] 8.1 在 `flutter_app/pubspec.yaml` 的 dependencies 新增 `record: ^5.0.0`，執行 `flutter pub get`
- [x] 8.2 建立 `flutter_app/test/unit/mic_recorder_test.dart`，測試 FakeMicRecorderService：stopAndGetBytes 回傳 fakeAudio、cancelRecording 不拋錯、cancel 後 stopAndGetBytes 回傳空 bytes（先確認 FAIL）
- [x] 8.3 建立 `flutter_app/lib/shared/mic/mic_recorder_service.dart`：定義 `MicRecorderService` abstract class（startRecording / stopAndGetBytes / cancelRecording / dispose）；`RealMicRecorderService` 用 `AudioRecorder` 錄音到暫存 WAV 檔，stopAndGetBytes 讀取後刪除檔案；`FakeMicRecorderService` 回傳 fakeAudio，cancel 後回傳空 bytes
- [x] 8.4 執行 `flutter test test/unit/mic_recorder_test.dart -v` 確認 3 passed

## 9. Flutter — BackendClient.qa()

- [x] 9.1 更新 `flutter_app/lib/shared/backend/backend_client.dart`：在 `BackendClient` abstract class 新增 `qa()` 方法簽名；`RealBackendClient` 實作 `qa()` — 建立 `MultipartRequest`，audio bytes 作為 multipart file，context JSON 作為 field，SSE 解析透過既有 SseParser，`transcript`/`text`/`audio`/`end`/`error` events 對應 QaEvent 子類別；`FakeBackendClient` 新增 `scriptedQaEvents` 欄位，qa() 逐一 yield
- [x] 9.2 執行 `flutter analyze` 確認無 error
- [x] 9.3 執行 `flutter test -v` 確認全部測試通過

## 10. Flutter — Providers 更新

- [x] 10.1 更新 `flutter_app/lib/shared/providers.dart`：新增 `narrationAudioPlayerProvider`（audioPlayerServiceProvider 的別名）、`qaAudioPlayerProvider`（獨立 RealAudioPlayerService 實例，有 onDispose）、`micRecorderProvider`（RealMicRecorderService 實例，有 onDispose）
- [x] 10.2 執行 `flutter test -v` 確認全部測試通過

## 11. Flutter — QaNotifier（TDD）

- [x] 11.1 建立 `flutter_app/test/unit/qa_provider_test.dart`，使用 FakeBackendClient + FakeMicRecorderService + FakeAudioPlayerService，測試：初始 status 是 idle、startRecording 後是 recording、startRecording duck 旁白音量、stopAndSend 經過 processing → answering 狀態轉換、stopAndSend 後 transcript 包含 TranscriptQaEvent 的文字、cancelRecording 後是 idle 且 unduck（先確認 FAIL）
- [x] 11.2 建立 `flutter_app/lib/features/qa/providers/` 目錄，建立 `qa_provider.dart`：定義 `QaStatus` enum（idle/recording/processing/answering/error）、`QaState` class（status/transcript/responseText/errorMessage）、`QaNotifier`（依賴注入 BackendClient/narrationAudio/qaAudio/mic）實作 startRecording（duck + mic.start + state=recording）、stopAndSend（guard <500ms → cancel；mic.stop → bytes → state=processing → stream事件處理）、cancelRecording（cancel stream + mic.cancel + unduck + state=idle）、_handleEvent（TranscriptQaEvent→answering+transcript；TextQaEvent→append responseText；AudioQaEvent→qaAudio.enqueue；EndQaEvent→unduck+idle；ErrorQaEvent→unduck+error）；定義 `qaProvider` StateNotifierProvider
- [x] 11.3 執行 `flutter test test/unit/qa_provider_test.dart -v` 確認 6 passed

## 12. Flutter — PushToTalkButton Widget

- [x] 12.1 建立 `flutter_app/test/widget/push_to_talk_button_test.dart`，使用 FakeSessionNotifier 和 ProviderScope overrides，測試：session active 時顯示 mic icon、session inactive 時不顯示 mic icon（先確認 FAIL）
- [x] 12.2 建立 `flutter_app/lib/features/qa/widgets/` 目錄，建立 `push_to_talk_button.dart`：`PushToTalkButton extends ConsumerWidget`，session inactive 時回傳 SizedBox.shrink；GestureDetector 的 onLongPressStart 呼叫 startRecording、onLongPressEnd 讀取 narrationProvider 和 sessionProvider context 呼叫 stopAndSend、onLongPressCancel 呼叫 cancelRecording；`_buildIcon()` 根據 QaStatus switch：idle=藍圈麥克風、recording=紅色脈衝動畫（_PulsingButton）、processing=CircularProgressIndicator、answering=藍圈喇叭、error=橘色警告
- [x] 12.3 執行 `flutter test test/widget/push_to_talk_button_test.dart -v` 確認 2 passed

## 13. Flutter — MapScreen 整合 PushToTalkButton

- [x] 13.1 更新 `flutter_app/lib/features/map/screens/map_screen.dart`：import PushToTalkButton；在 body Stack 的 NarrationSheet 之後新增 `Positioned(bottom: 100, child: Center(child: PushToTalkButton()))`
- [x] 13.2 執行 `flutter analyze` 確認無 error
- [x] 13.3 執行 `flutter test -v` 確認全部通過

## 14. Flutter — NarrationSheet Q&A 字幕

- [x] 14.1 更新 `flutter_app/lib/features/narration/widgets/narration_sheet.dart`：import QaProvider；在 subtitle Text widget 前插入 Consumer，當 qa.status != idle 或 qa.transcript 非空時顯示 Q&A 字幕區塊（深藍背景、「你說：...」transcript + 回覆文字 responseText）
- [x] 14.2 執行 `flutter test -v` 確認全部通過
- [x] 14.3 執行 `flutter analyze` 確認無 error

## 15. 最終驗收

- [x] 15.1 執行 `cd backend && .venv/bin/pytest -v` 確認全部 backend 測試通過（0 failed）
- [x] 15.2 執行 `cd flutter_app && flutter test -v` 確認全部 Flutter 測試通過（0 failed）
- [x] 15.3 執行 `cd flutter_app && flutter analyze` 確認 No issues found（或僅 info 層級）
- [ ] 15.4 手動驗收：啟動後端，curl 測試 `/qa` endpoint 可收到 `transcript`、`text`、`audio`、`end` SSE events；或用模擬器確認長按 PushToTalkButton 出現錄音動畫、放開後觸發問答流程
