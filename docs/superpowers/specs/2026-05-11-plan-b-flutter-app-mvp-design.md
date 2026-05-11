# Plan B: Flutter App MVP — Design Spec

| 欄位 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 撰寫日期 | 2026-05-11 |
| 適用範圍 | Plan B — Flutter App MVP，消費 Plan A 後端三個 endpoint |
| 前置條件 | Plan A 後端完成（GET /health, GET /poi/nearby, POST /narration SSE）|
| 後續文件 | Plan B Implementation Plan（待建立）|

---

## 1. Goals / Non-Goals

**Goals:**
- 建立 Flutter App 專案骨架（iOS + Android 雙平台）
- 實作兩個主畫面：HomeScreen + MapScreen（含 NarrationSheet）
- 前景定位 + 附近 POI 顯示（互動地圖 + 標記點）
- 手動觸發（點 POI 標記）+ 自動觸發（進入 100m 範圍）旁白播放
- SSE 串流解析 → FIFO 音訊佇列播放（just_audio）
- Drift SQLite（cooldown / history schema）
- 完整測試套件：unit / widget / integration（完全離線，FakeBackendClient）

**Non-Goals（明確排除）:**
- Push-to-talk Q&A（Plan D）
- 背景定位（Plan F）
- Settings UI（dart-define 替代）
- 多 persona 選擇（Plan C；Plan B 只有 history_uncle）
- 食家 persona / Google Places（Plan E）
- 歷史紀錄頁（schema 先存好，UI Plan C 後加）
- Cloud Run 部署 + API Key 保護（Plan F）

---

## 2. 畫面結構與導航

Plan B 共 **2 個主畫面** + **1 個底部 Sheet overlay**：

```
HomeScreen
  └─ [開始旅程] → 申請定位權限 → MapScreen
       └─ NarrationSheet（overlay，可上滑展開 / 下滑收合）
            ├─ 收合：Mini bar（POI 名 + 播放控制）
            └─ 展開：字幕 + 進度條 + 控制鈕
```

### HomeScreen
- 顯示 App 名稱、當前 persona（history_uncle）、搜尋半徑
- 「開始旅程」按鈕 → `SessionProvider.start()` → 申請定位權限 → push MapScreen
- 定位權限被拒 → 顯示引導對話框

### MapScreen
- AppBar：「旅程進行中 🔵」+ 「結束」按鈕
- GoogleMap 全版，顯示 POI 標記點（按 confidence 用不同顏色）
- 使用者位置藍點追蹤
- 點 POI 標記 → 手動觸發旁白
- NarrationSheet 在地圖上層

### NarrationSheet（DraggableScrollableSheet）
- **收合狀態**：Mini bar（POI 名稱 + 距離 + ▶/⏸ + ⏭）
- **展開狀態**：POI 名稱、confidence 標籤、滾動字幕、進度條、⏸/⏭/🔁 控制

---

## 3. 模組結構（Feature-based）

```
flutter_app/
├── pubspec.yaml
├── dart_defines/
│   └── dev.json                    ← {"BACKEND_URL":"http://10.0.2.2:8000"}
├── lib/
│   ├── main.dart                   ← ProviderScope + runApp
│   ├── app.dart                    ← MaterialApp + go_router
│   │
│   ├── features/
│   │   ├── session/
│   │   │   ├── providers/session_provider.dart    ← idle/starting/active/ending
│   │   │   ├── screens/home_screen.dart
│   │   │   └── widgets/persona_chip.dart
│   │   │
│   │   ├── map/
│   │   │   ├── providers/poi_provider.dart        ← /poi/nearby 呼叫 + 快取
│   │   │   ├── screens/map_screen.dart
│   │   │   └── widgets/poi_marker.dart
│   │   │
│   │   └── narration/
│   │       ├── providers/narration_provider.dart  ← SSE stream + 播放狀態
│   │       ├── providers/trigger_provider.dart    ← TriggerEngine
│   │       ├── widgets/narration_sheet.dart
│   │       └── widgets/narration_mini_bar.dart
│   │
│   └── shared/
│       ├── backend/
│       │   ├── backend_client.dart                ← HTTP + SSE（dart-define URL）
│       │   └── models/                            ← POI, NarrationEvent, PersonaConfig
│       ├── audio/
│       │   └── audio_player_service.dart          ← just_audio 包裝
│       ├── location/
│       │   └── location_service.dart              ← geolocator 包裝
│       └── db/
│           └── local_db.dart                      ← drift（cooldown / history）
│
└── test/
    ├── unit/
    │   ├── trigger_engine_test.dart
    │   ├── sse_parser_test.dart
    │   └── haversine_test.dart
    ├── widget/
    │   ├── narration_sheet_test.dart
    │   └── home_screen_test.dart
    └── integration/
        └── narration_flow_test.dart               ← FakeBackendClient
```

### 關鍵 packages

| 用途 | 套件 |
|---|---|
| State management | `flutter_riverpod` + `riverpod_annotation` |
| 互動地圖 | `google_maps_flutter` |
| 定位 | `geolocator` + `permission_handler` |
| 音訊播放 | `just_audio` |
| 本地 DB | `drift` |
| HTTP / SSE | `http`（自訂 SseParser） |
| 路由 | `go_router` |
| 音訊 temp 路徑 | `path_provider` |

---

## 4. Provider 設計

### SessionProvider（StateNotifier）

```dart
enum SessionStatus { idle, starting, active, ending }

class SessionState {
  final SessionStatus status;
  final String persona;       // Plan B 固定 "history_uncle"
  final String lang;          // Plan B 固定 "zh-TW"
}
```

- `start()` → 申請定位權限 → 啟動 LocationService → status = active
- `stop()` → 停止 LocationService / TriggerProvider → 寫 DB session.ended_at → status = idle

### PoiProvider（AsyncNotifier）

- Watch `LocationService.positionStream`，移動 >250m 重新 fetch `/poi/nearby`
- 回傳 `List<POI>` 依距離排序

### NarrationProvider（StateNotifier）

```dart
class NarrationState {
  final NarrationStatus status;  // idle/loading/playing/paused/error
  final POI? currentPoi;
  final String subtitle;         // 累積字幕
  final double progress;         // 0.0~1.0
  final String? confidence;      // high/medium/low
}
```

- `narrate(POI)` → 開啟 SSE → 解析 events → 餵 AudioPlayerService
- `pause()` / `resume()` / `skip()`
- 播完 → `LocalDB.cooldown.set(poi.id, 24h)` + `LocalDB.history.add(...)`

### TriggerProvider（自動觸發）

- Watch `(positionStream, poiList)` 組合
- 對每個 POI 做 `haversine(pos, poi) < 100m`
- 不在 cooldown → emit trigger → `NarrationProvider.narrate(poi)`
- 同 session 已播過的 POI dedup（in-memory Set）

---

## 5. 核心資料流

### Flow 1：自動觸發路徑

```
LocationService → positionStream (每 5s)
  ↓ 移動 >250m
PoiProvider.fetch() → GET /poi/nearby → List<POI>
  ↓
TriggerProvider.evaluate(position, poiList)
  ├─ haversine < 100m?
  ├─ LocalDB.cooldown.has(poi.id)? → skip
  └─ 通過 → NarrationProvider.narrate(poi)
```

### Flow 2：SSE 串流 → 音訊播放

```
BackendClient.narrate(poi) → http.Client.send(POST /narration)
  ↓
SseParser.parse(byteStream) → Stream<SseEvent>
  ├─ event: meta  → NarrationProvider 更新 confidence
  ├─ event: text  → NarrationProvider 累積字幕
  ├─ event: audio → base64.decode() → temp file → AudioPlayerService.enqueue()
  ├─ event: end   → 標記完成 → cooldown + history 寫 DB
  └─ event: error → NarrationProvider 進入 error 狀態
```

### Flow 3：音訊 FIFO 播放

```
AudioPlayerService（just_audio ConcatenatingAudioSource）
  ├─ 第一個 audio chunk 到達 → 立即開始播放（首字延遲 ~2s）
  ├─ 後續 chunks 陸續 enqueue → 連續播放
  └─ session 結束 → 清除 getTemporaryDirectory() 下的 mp3 temp files
```

### 手動觸發（簡化路徑）

使用者點地圖 POI 標記 → 直接呼叫 `NarrationProvider.narrate(poi)`，跳過 TriggerProvider。

---

## 6. 後端連線設定

使用 `--dart-define` 注入，不做 Settings UI：

```bash
# iOS Simulator
flutter run --dart-define=BACKEND_URL=http://localhost:8000

# Android Emulator
flutter run --dart-define=BACKEND_URL=http://10.0.2.2:8000

# 真機（後端跑本機時需同 WiFi）
flutter run --dart-define=BACKEND_URL=http://192.168.x.x:8000
```

`dart_defines/dev.json` 提供預設值，`BackendClient` 在建構時讀取：

```dart
const backendUrl = String.fromEnvironment('BACKEND_URL', defaultValue: 'http://localhost:8000');
```

---

## 7. 本地 DB Schema（drift）

Plan B 建立 schema，UI 在後續 Plan 加：

```sql
-- Session 紀錄
CREATE TABLE sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at INTEGER NOT NULL,
  ended_at INTEGER,
  persona TEXT NOT NULL,
  lang TEXT NOT NULL
);

-- 旁白播放紀錄（cooldown + 歷史）
CREATE TABLE narration_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  poi_id TEXT NOT NULL,
  poi_name TEXT NOT NULL,
  poi_lat REAL NOT NULL,
  poi_lon REAL NOT NULL,
  persona TEXT NOT NULL,
  lang TEXT NOT NULL,
  played_at INTEGER NOT NULL,
  completed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_narration_poi_time ON narration_history(poi_id, played_at DESC);
```

Cooldown 查詢：`SELECT 1 FROM narration_history WHERE poi_id = ? AND played_at > ? LIMIT 1`

---

## 8. 錯誤處理

| 情境 | 行為 |
|---|---|
| 定位權限被拒 | HomeScreen 顯示引導對話框 + 直達設定按鈕 |
| 後端無回應 / 5xx | BackendClient 重試 3 次（1s/2s/4s）；失敗後 NarrationProvider → error 狀態 |
| SSE 串流中途斷線 | AudioPlayer 播完已 enqueue 部分後停止；顯示 snackbar |
| Gemini 429（SSE error event）| NarrationProvider 讀 `retry_after_s`，顯示倒數 snackbar |
| GPS 精度差（>100m） | TriggerProvider 暫停評估；MapScreen 顯示「定位精度不足」badge |
| 後端回 429（/poi/nearby）| PoiProvider 暫停輪詢，等 `Retry-After` 後重試 |

---

## 9. 測試策略

### Unit tests（TDD，最大宗）

| 模組 | 測試什麼 |
|---|---|
| `TriggerEngine` | 距離計算、cooldown skip、dedup、觸發序列 |
| `SseParser` | 解析 meta/text/audio/end/error event；partial chunk 邊界 |
| `haversine()` | 距離計算正確性與邊界值 |
| `SessionProvider` | 狀態機轉換 |

### Widget tests

| 元件 | 測試什麼 |
|---|---|
| `NarrationSheet` | 收合 / 展開、字幕更新、按鈕狀態 |
| `HomeScreen` | 按鈕觸發 session.start()、權限拒絕提示 |

### Integration tests（完全離線）

- `FakeBackendClient`：模擬 `/poi/nearby` + SSE event 序列
- 測試 `NarrationProvider` 從 narrate() 到 end event 的完整 state 變化
- Drift in-memory DB 測試 cooldown 寫入 / 查詢

### 不做的測試（YAGNI）

- 真實 Google Maps 渲染
- 音訊實際播放品質
- 背景定位行為（Plan F）

---

## 10. 開放問題

- Google Maps API Key 申請與 iOS / Android 各自的設定方式需在 Task 1 確認
- `just_audio` 的 `ConcatenatingAudioSource` 動態 append 在 iOS 與 Android 的行為需 smoke test 驗證
- SSE base64 音訊 chunk 大小（Plan A 後端按句子切分），first chunk 延遲預期 ~2s，需真機確認
