## Why

Plan A 後端（FastAPI）已完成三個 endpoint（`GET /health`、`GET /poi/nearby`、`POST /narration` SSE），需要一個 Flutter 行動端 MVP 來消費這些 API，讓使用者能在旅途中透過手機自動或手動觸發附近 POI 的語音旁白。

## What Changes

- 新增 `flutter_app/` Flutter 專案骨架（iOS + Android 雙平台）
- 實作 HomeScreen（選擇 persona、開始旅程）與 MapScreen（互動地圖 + POI 標記）
- 實作 NarrationSheet（底部 DraggableScrollableSheet，收合 MiniBar + 展開字幕控制）
- 實作前景定位 + 附近 POI 自動刷新（移動 >250m）
- 實作 TriggerEngine：使用者進入 POI 100m 範圍自動觸發旁白
- 實作手動觸發：點擊地圖 POI 標記直接播放
- 實作 SSE 串流解析 → FIFO 音訊佇列（just_audio ConcatenatingAudioSource）
- 實作 Drift SQLite 儲存 session 與旁白歷史（cooldown 24h dedup）
- 完整測試套件：unit / widget / integration（完全離線，FakeBackendClient）

## Capabilities

### New Capabilities

- `tour-session`: Session 生命週期管理（idle/starting/active/ending）、定位權限申請、HomeScreen UI
- `poi-map`: 附近 POI 查詢（`/poi/nearby`）、Google Maps 互動地圖、POI 標記點依 confidence 著色
- `narration-stream`: SSE 串流解析（SseParser）、base64 音訊解碼、just_audio FIFO 佇列播放、NarrationSheet 字幕顯示
- `trigger-engine`: haversine 距離計算、TriggerEngine 自動觸發（100m 半徑）、cooldown / dedup 邏輯
- `local-storage`: Drift SQLite schema（sessions + narration_history）、cooldown 查詢、旁白歷史寫入

### Modified Capabilities

（無——此為全新 Flutter 端，Plan A 後端 API 介面不變）

## Impact

- 新增 `flutter_app/` 目錄（Flutter 3.x / Dart 3.x 專案）
- 依賴 Plan A 後端三個 endpoint（本地開發透過 `--dart-define=BACKEND_URL` 注入）
- 新增 packages：`flutter_riverpod`、`google_maps_flutter`、`geolocator`、`just_audio`、`drift`、`http`、`go_router`、`path_provider`
- 需申請 Google Maps API Key（iOS + Android 各自設定）
- 無影響現有後端程式碼
