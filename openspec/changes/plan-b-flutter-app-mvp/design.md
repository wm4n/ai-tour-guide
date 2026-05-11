## Context

Plan A 後端（FastAPI on Python）已實作並通過全套測試，提供三個 endpoint：
- `GET /health` — 健康檢查
- `GET /poi/nearby` — 查詢附近 POI（lat/lon/radius）
- `POST /narration` — SSE 串流旁白（event: meta/text/audio/end/error）

本設計為 Plan B Flutter App MVP，消費上述 API，實現「行走時自動觸發附近 POI 語音旁白」的核心體驗。

**約束：**
- 只支援前景定位（不做背景定位）
- 只有一個 persona：`history_uncle`
- 不做 Settings UI，所有設定透過 dart-define 注入
- Google Maps API Key 需申請（iOS + Android 各別設定）

## Goals / Non-Goals

**Goals:**
- Flutter 3.x / Dart 3.x 雙平台（iOS + Android）專案骨架
- HomeScreen + MapScreen + NarrationSheet 三個畫面
- 前景定位 + 附近 POI 刷新（移動 >250m）
- 自動觸發（進入 100m）+ 手動觸發（點標記）旁白播放
- SSE 串流解析 → FIFO 音訊佇列（just_audio）
- Drift SQLite cooldown / history schema
- 完整測試套件：unit / widget / integration（完全離線）

**Non-Goals:**
- Push-to-talk Q&A、背景定位、Settings UI
- 多 persona 選擇、歷史紀錄頁 UI、Cloud Run 部署

## Decisions

### 1. Feature-based Riverpod 架構（over layered / screen-based）

Feature-based：每個 feature（session/map/narration）有自己的 providers/screens/widgets。
- **採用原因**：feature 之間 import 邊界清楚，shared/ 只放跨 feature 的基礎設施；相較 layered 架構，不同 feature 的變更不會互相影響；相較 screen-based，provider 可跨 widget 共享而不重複。

### 2. BackendClient / LocationService / AudioPlayerService 抽象介面（for testability）

每個外部依賴都定義 abstract class，提供 `Real*` 和 `Fake*` 兩種實作。
- **採用原因**：整合測試需要完全離線；`Fake*` 可精確控制 SSE event 序列和位置流，不依賴任何 mock 框架。

### 3. dart-define 注入 BACKEND_URL（over Settings UI）

```bash
flutter run --dart-define-from-file=dart_defines/dev.json
```
- **採用原因**：Settings UI 屬於 Non-Goal；dart-define 在 build 時注入，不需要任何 runtime UI；`dart_defines/dev.json` 提供預設值讓新開發者零設定啟動。

### 4. 自訂 SseParser（over sse_client 等 package）

純靜態 class，對 `Stream<List<int>>` 做 UTF-8 decode + `\n\n` 分塊解析。
- **採用原因**：Plan A 後端 SSE 格式固定（event: type + data: JSON），不需要完整 EventSource 實作；自訂解析器可精確測試 partial chunk 邊界行為。

### 5. just_audio ConcatenatingAudioSource（over 手動 queue）

每個 audio chunk decode 成 temp file，append 到 `ConcatenatingAudioSource`。
- **採用原因**：just_audio 原生支援動態 append，不需要手動管理播放狀態機；第一個 chunk 到達即可開始播放，後續 chunk 自動銜接，首字延遲 ~2s。
- **風險**：iOS/Android 行為需 smoke test 驗證（見 Open Questions）。

### 6. Drift + drift_flutter（over sqflite / Hive）

- **採用原因**：type-safe 查詢、code generation、`forTesting(NativeDatabase.memory())` 讓 unit test 零依賴；schema 易於未來版本升級。

## Risks / Trade-offs

- **Google Maps API Key 設定繁瑣** → 在 Task 1 建立 flutter_app 骨架時加入明確的 AndroidManifest + AppDelegate 設定步驟，提前阻斷。
- **ConcatenatingAudioSource 動態 append 在 iOS 行為未確認** → Task 完成後需在真機 smoke test；若有問題，退路是手動播放佇列（播完一個再 setAudioSource 下一個）。
- **SSE base64 audio chunk 大小不固定** → SseParser 以 `\n\n` 分塊，與 chunk 大小無關；just_audio temp file 策略不受影響。
- **dart-define 在 IDE run configuration 容易漏設** → `dart_defines/dev.json` 提供預設值，`BackendClient` 有 `defaultValue: 'http://localhost:8000'`。

## Open Questions

1. Google Maps API Key 申請後，iOS 需設定 `AppDelegate.swift`，Android 需設定 `AndroidManifest.xml`；需確認兩平台 Key 是否共用或分開。
2. `just_audio` `ConcatenatingAudioSource` 動態 append 在 iOS 與 Android 的行為需 smoke test 驗證。
3. SSE audio chunk 大小（後端按句子切分），first chunk 延遲預期 ~2s，需真機確認是否可接受。
