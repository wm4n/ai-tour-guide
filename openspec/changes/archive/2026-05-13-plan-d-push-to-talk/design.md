## Context

AI Tour Guide App 目前（Plan C 完成後）具備以下能力：
- MapScreen 顯示附近 POI，使用者啟動 session 後會觸發自動旁白
- 旁白透過 `NarrationService`（LLM → TTS）串流，Flutter 端用 `AudioPlayerService`（just_audio）播放
- 支援 Persona 系統（歷史大叔/英語導覽員）和雙語切換（zh-TW/en）
- 後端 `PromptBuilder` 組裝 narration prompt，有 `LlmProvider`、`TtsProvider` 抽象介面

Plan D 的目標是在此基礎上新增 Push-to-talk Q&A：使用者長按麥克風按鈕錄音，後端進行 STT → LLM → TTS 串流回答，旁白音量降至 50%（ducking）但不暫停，Q&A 音訊由獨立第二個 AudioPlayer 播放。

**關鍵約束：**
- Q&A 無快取、無 cooldown/history 寫入（每次都是全新呼叫）
- 錄音時長 < 500ms 視為誤觸，靜默取消
- 旁白繼續播放（duck 至 50%），不暫停

## Goals / Non-Goals

**Goals:**
- 新增 `SttProvider` 抽象介面（Protocol + `GeminiSttAdapter` + `FakeSttProvider`）以利測試與替換
- 新增 `QAService`：orchestrates STT → PromptBuilder.build_qa() → LLM → TTS pipeline，產生 SSE 事件流
- 新增 `POST /qa` endpoint：接收 multipart audio + context JSON，回傳 SSE 事件（transcript / text / audio / end / error）
- 擴充 `PromptBuilder.build_qa()`：支援有/無 POI context 兩個分支
- Flutter 新增 `MicRecorderService`（WAV 格式，`record ^5.0`）
- Flutter 新增 `QaNotifier`（Riverpod StateNotifier）管理 Q&A 狀態機（idle / recording / processing / answering / error）
- Flutter 新增 `PushToTalkButton` widget 整合至 MapScreen 底部
- Flutter 擴充 `AudioPlayerService.duck() / unduck()`，Q&A 期間旁白音量降至 50%
- Flutter 新增 `qaAudioPlayerProvider`（獨立第二個 AudioPlayer 實例）播放 Q&A 音訊
- Flutter 擴充 `BackendClient.qa()`：multipart POST + SSE 解析
- Flutter 擴充 `NarrationSheet`：Q&A 進行中時在旁白字幕上方顯示 transcript 和回覆文字

**Non-Goals:**
- VAD（Voice Activity Detection）自動停止錄音 — Plan D 使用明確的 push-to-talk 邊界
- 問答歷史記錄（LocalDB）— 規劃在 Plan F
- Q&A 旁白字幕時間對齊
- 背景錄音（push-to-talk 只在前景使用）
- 多輪對話（每次 Q&A 獨立，無 history context）

## Decisions

### 決策 1：使用獨立第二個 AudioPlayer 播放 Q&A 音訊

**選擇：** 新增 `qaAudioPlayerProvider`，建立完全獨立的 `RealAudioPlayerService` 實例

**理由：** just_audio 的 `ConcatenatingAudioSource` 是線性佇列，混入 Q&A 音訊會干擾旁白的播放順序。獨立實例讓 Q&A 音訊完全隔離，duck/unduck 只作用在旁白 player，不影響 Q&A 音量。

**備選方案：** 使用同一個 player 並插入 Q&A 音訊（被否決：佇列順序難以管理，Q&A 結束後很難清理旁白繼續點）

---

### 決策 2：旁白 duck 至 50%，不暫停

**選擇：** `AudioPlayerService.duck()` 呼叫 `setVolume(0.5)`，Q&A 結束後 `unduck()` 呼叫 `setVolume(1.0)`

**理由：** 暫停旁白會讓使用者失去空間感，duck 保持旁白連貫性，且 just_audio 的 `setVolume()` 是即時生效的。

**備選方案：** 暫停旁白（被否決：使用者體驗較差；但若 Q&A 音量仍影響理解，可在 Plan E 改為暫停）

---

### 決策 3：SSE 事件格式 — Q&A 重用 narration 的 text/audio/end/error，新增 transcript

**選擇：** Q&A SSE 事件序列：`transcript → text+audio（交錯）→ end`；`transcript` 為 Q&A 獨有，其他事件型別與 narration 相同

**理由：** 重用既有 SSE 解析基礎設施（`SseParser`、`encode_event()`），減少重複代碼；`transcript` event 讓 Flutter 即時顯示「你說：...」

**備選方案：** 定義全新的 Q&A 事件型別（被否決：增加前後端協議複雜度，且解析邏輯幾乎一樣）

---

### 決策 4：後端使用 `current_poi_name`（名稱）而非 `current_poi_id`（ID）傳入 PromptBuilder

**選擇：** `/qa` endpoint 收到 `current_poi_id` 後，直接以 ID 字串當 poi_name 傳入 `build_qa()`（不做 ID→name lookup）

**理由：** Plan D 的目標是快速可用，POI name lookup 需要額外的 DB 或 cache 查詢。ID 字串在 prompt 中雖不理想，但功能上可運作。Name 正確化可在後續計畫中優化。

**備選方案：** 從 POICache 查詢 poi_name（被否決：增加 `/qa` endpoint 複雜度，且 Plan D 驗收標準不包含此點）

---

### 決策 5：錄音格式選用 WAV

**選擇：** `record` 套件設定 `AudioEncoder.wav`

**理由：** WAV 格式無壓縮、無編碼依賴，後端（Gemini STT API / `google-genai`）解析最直接；`record ^5.0` 在 iOS/Android 對 WAV 支援最穩定。

**備選方案：** AAC/MP3（被否決：Android 部分裝置需額外 codec；Gemini STT 雖支援，但增加後端 mime type 判斷）

---

### 決策 6：QaNotifier 使用 `StateNotifier`（非 `AsyncNotifier`）

**選擇：** `class QaNotifier extends StateNotifier<QaState>`

**理由：** Q&A 狀態轉換複雜（idle→recording→processing→answering→idle），且需要在多個地方呼叫 duck/unduck side effect。`StateNotifier` 的同步 `state =` 賦值更直觀；`_handleEvent()` 中的事件處理不需要 async 生命週期管理。

**備選方案：** `AsyncNotifier` 或 Riverpod `stream provider`（被否決：事件處理需要同步更新多個欄位，`AsyncNotifier` 的 `AsyncValue` 包裝會增加 UI 端複雜度）

## Risks / Trade-offs

**[Risk] WAV 檔案大小** → WAV 無壓縮，30 秒錄音約 2.8MB（44.1kHz/16bit）。Plan D 的典型問題短於 10 秒，約 900KB。若網路較慢，上傳時間可能讓使用者感覺 latency 偏高。
*Mitigation:* 在 `QaNotifier.stopAndSend()` 加入「錄音中」動畫反饋，讓使用者知道正在處理；未來可改用 Opus 格式壓縮。

**[Risk] Q&A 播放中再次長按** → 需要 cancel 當前 stream + `_qaAudio.skip()` + unduck → 重新 startRecording。
*Mitigation:* `QaNotifier.startRecording()` 開頭呼叫 `_sub?.cancel()` 取消前一個 Q&A stream；已在設計中明確處理。

**[Risk] Session 結束時 Q&A 仍在進行** → 若使用者在 Q&A 播放中結束 session，旁白 duck 狀態未被清除。
*Mitigation:* `MapScreen` 監聽 `sessionProvider.isActive` 變化，當 `isActive == false` 時呼叫 `qaProvider.notifier.cancelRecording()`。

**[Risk] `record ^5.0` iOS 麥克風權限** → iOS 需要在 `Info.plist` 加入 `NSMicrophoneUsageDescription`，否則 App 直接 crash。
*Mitigation:* Task 8 明確標注需更新 `ios/Runner/Info.plist`；FakeMicRecorderService 讓測試可在不需要真實麥克風的環境執行。

**[Trade-off] current_poi_name 用 ID 替代** → Prompt 中出現 `osm:way:12345` 而非「故宮博物院」，LLM 可能無法正確 ground 問題。
*Mitigation:* 屬於已知 Plan D 限制，可接受；POI name 正確化列入後續優化 backlog。

## Migration Plan

1. **後端部署**：新增 `/qa` endpoint 是純新增，不影響現有 `/narration`、`/poi` endpoint；main.py 新增 QAService DI 即可
2. **Flutter 更新**：`AudioPlayerService` 介面新增 `duck()`/`unduck()` — 現有 `RealAudioPlayerService` 和 `FakeAudioPlayerService` 都需實作；現有呼叫端不受影響（只是新增方法）
3. **Rollback**：若 `/qa` endpoint 出現問題，可從 main.py 移除 qa router，Flutter 端 `PushToTalkButton` 只在 session active 時顯示，不影響主流程
4. **pubspec.yaml 更新**：新增 `record: ^5.0.0` 需要所有開發者執行 `flutter pub get`，iOS 需更新 `Info.plist`

## Open Questions

- **POI Name 解析**：`/qa` endpoint 目前用 `current_poi_id` 字串直接當 poi_name 傳入 prompt，若 LLM 對 ID 字串回答品質不佳，需考慮在 Plan E 加入 POI cache lookup
- **iOS 麥克風測試**：`record ^5.0` 在 iOS simulator 上的行為需實機驗證，FakeMicRecorderService 可確保 CI 測試正常，但實際錄音品質需人工驗收
- **Gemini STT rate limit**：若多人同時使用 push-to-talk，Gemini STT API 的 rate limit 是否足夠？目前無 retry logic 以外的處理
