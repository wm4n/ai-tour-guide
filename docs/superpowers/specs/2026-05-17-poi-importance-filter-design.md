# POI 重要性過濾 + 位移等待設計文件

**日期**: 2026-05-17
**分支**: feat/plan-b-flutter-app-mvp

---

## 問題背景

目前 `POISelectorService` 在收到候選 POI 清單後必定選出一個來旁白，即使所有候選都是不值得說明的瑣碎景點（地圖看板、導覽牌、公車站牌等），仍會觸發 LLM 旁白並浪費 token。同時，跨越這些瑣碎景點後，倒數計時仍然繼續，導致無限觸發。

---

## 目標

1. LLM 能判斷「目前所有候選都不值得說」，回傳 SKIP 信號
2. 收到 SKIP 後，App 停止倒數，改為等待用戶位移至少 1.5km（可設定）後才重觸發
3. Badge UI 顯示「移動中」狀態，讓用戶知道 App 在等什麼
4. 新增設定頁面，讓用戶調整位移門檻與倒數秒數

---

## 架構設計

### 資料流

```
用戶移動
  → trigger_provider._doCandidatesRequest()
  → backend POST /narration (candidates)
  → POISelectorService.select()
      ├─ 回傳 poi_id → NarrationService.narrate() → SSE stream (現有行為)
      └─ 回傳 None (SKIP) → 串流 skip 事件後關閉
  → Flutter 收到 SkipEvent
      → TriggerState.isWaitingForDisplacement = true
      → 記錄 skipLat / skipLon
      → 訂閱 location，監測位移距離
      → 距離 > threshold → 重觸發
```

---

## Backend 設計

### 1. `POISelectorService.select()` 回傳值變更

```python
async def select(...) -> str | None:
    """Return poi_id of best candidate, or None if all candidates are trivial."""
```

**Prompt 新增 SKIP 規則**：

```
SKIP rule — reply with only "SKIP" if ALL candidates are trivial:
- Trivial examples: maps/signs/boards/bus markers
  (名稱含 地圖 / map / 導覽圖 / 公車 / 巴士 / bus / signboard / information board 等)
- Trivial: no Wikipedia data AND name clearly indicates infrastructure/signage
- Worth narrating: has Wikipedia data, OR is a named attraction/monument/building/park/temple
If even ONE candidate is worth narrating, pick the best one as usual.
Reply with ONLY the poi_id or ONLY the word SKIP — nothing else.
```

**回傳處理**：
- 若 LLM 回傳 `"SKIP"` → return `None`
- 若 LLM 回傳無效 id 且非 `"SKIP"` → fallback to `candidates[0].poi_id`（保留現有行為）

### 2. `narration.py` Endpoint 處理 SKIP

```python
selected_id = await poi_selector.select(request.candidates, persona, request.lang, request.previous_selection)

if selected_id is None:
    # Stream a single skip event and close
    async def skip_stream():
        yield "event: skip\ndata: {\"min_displacement_m\": 1500.0}\n\n"
    return StreamingResponse(skip_stream(), media_type="text/event-stream")
```

### 3. 新增 `SkipEvent` dataclass（`narration_service.py` 或 `models/`）

```python
@dataclass
class SkipEvent:
    min_displacement_m: float = 1500.0
```

### 4. Log Event

`log_events.py` 新增：
```python
POI_SELECTION_SKIP = "POI_SELECTION_SKIP"
```

---

## Flutter 設計

### 1. `NarrationEvent` 新增 `SkipEvent`

```dart
// narration_event.dart
class SkipEvent extends NarrationEvent {
  final double minDisplacementM;
  const SkipEvent({this.minDisplacementM = 1500.0});

  factory SkipEvent.fromJson(Map<String, dynamic> json) =>
      SkipEvent(minDisplacementM: (json['min_displacement_m'] as num?)?.toDouble() ?? 1500.0);
}
```

SSE 解析：event type `skip` → `SkipEvent.fromJson(data)`

### 2. `AppSettings` 模型 + Provider

```dart
// shared/settings/app_settings.dart
class AppSettings {
  final double skipDisplacementM;   // 預設 1500.0
  final int countdownSeconds;       // 預設 90

  const AppSettings({
    this.skipDisplacementM = 1500.0,
    this.countdownSeconds = 90,
  });

  AppSettings copyWith({double? skipDisplacementM, int? countdownSeconds}) => ...;
}
```

```dart
// shared/settings/settings_provider.dart
class AppSettingsNotifier extends Notifier<AppSettings> {
  static const _keyDisplacement = 'skip_displacement_m';
  static const _keyCountdown = 'countdown_seconds';

  @override
  AppSettings build() {
    // Load from SharedPreferences on init
    ...
  }

  Future<void> setSkipDisplacement(double meters) async { ... }
  Future<void> setCountdownSeconds(int seconds) async { ... }
}

final appSettingsProvider = NotifierProvider<AppSettingsNotifier, AppSettings>(
  AppSettingsNotifier.new,
);
```

### 3. `TriggerState` 擴充

```dart
class TriggerState {
  final bool isCountingDown;
  final Duration countdownRemaining;
  final bool isWaitingForDisplacement;  // 新增
  final double? skipLat;                 // 新增
  final double? skipLon;                 // 新增
  final double movedMeters;              // 新增（顯示進度用）
}
```

### 4. `TriggerProvider` 擴充

**SkipEvent 處理**（在 `narrationProvider` listener 中）：

```dart
// 當 NarrationState 收到 skip（新增 NarrationStatus.skipped 或透過 event 通知）
if (next.lastEventWasSkip) {
  final loc = ref.read(locationServiceProvider).lastKnownPosition;
  state = state.copyWith(
    isWaitingForDisplacement: true,
    skipLat: loc?.latitude,
    skipLon: loc?.longitude,
    movedMeters: 0,
  );
  _startDisplacementWatch();
}
```

**位移監測**：

```dart
void _startDisplacementWatch() {
  _locationSub?.cancel();
  _locationSub = ref.read(locationServiceProvider).positionStream.listen((pos) {
    if (!state.isWaitingForDisplacement) return;
    final dist = _haversine(state.skipLat!, state.skipLon!, pos.latitude, pos.longitude);
    final threshold = ref.read(appSettingsProvider).skipDisplacementM;
    state = state.copyWith(movedMeters: dist);
    if (dist >= threshold) {
      _clearDisplacementWatch();
      _doCandidatesRequest();
    }
  });
}
```

**倒數秒數從設定取得**：

```dart
// 在 _startCountdown() 內直接讀取，而非 static const
final seconds = ref.read(appSettingsProvider).countdownSeconds;
final duration = Duration(seconds: seconds);
```

### 5. `CountdownBadge` 視覺擴充

| 狀態 | 樣式 |
|---|---|
| `isCountingDown` | 黑底，圓形倒數進度，顯示剩餘秒數（現有） |
| `isWaitingForDisplacement` | 灰底，步行圖示，顯示 `x.x / 1.5km` 進度 |
| 其他 | `SizedBox.shrink()` |

### 6. `SettingsScreen`

**路由**：從 `MapScreen` AppBar 右上角新增 ⚙️ IconButton 進入。

**內容**：

```
┌─────────────────────────────────────┐
│  設定                            ← │
├─────────────────────────────────────┤
│  旁白間隔                           │
│  [====●==========] 90 秒            │
│  30s ─────────────────────── 300s  │
├─────────────────────────────────────┤
│  略過景點後的移動距離門檻            │
│  [==========●====] 1500 m           │
│  500m ─────────────────────── 5km  │
└─────────────────────────────────────┘
```

---

## NarrationState 擴充

為了讓 TriggerProvider 能感知 SkipEvent，`NarrationState` 需要新增：

```dart
final bool lastEventWasSkip; // 當收到 SkipEvent 時設為 true，下次開始播放時清除
```

`NarrationNotifier` 在解析 SSE 事件時，遇到 `SkipEvent` → 設 `lastEventWasSkip = true`，status 維持 `idle`。

---

## 測試策略

### Backend
- `test_poi_selector.py`：新增 SKIP 回傳案例（LLM 回 "SKIP" → None）
- `test_narration_api.py`：當 selector 回 None，endpoint 回傳 skip SSE event

### Flutter
- `trigger_provider_test.dart`：
  - 收到 SkipEvent 後 `isWaitingForDisplacement` 為 true
  - 位移超過門檻後重觸發
  - 位移不足時不觸發
- `settings_provider_test.dart`：設定讀寫正確

---

## 新增依賴

- `shared_preferences: ^2.x` — 需加入 `flutter_app/pubspec.yaml`

---

## 不在範圍內

- Google Places 評分整合（資料結構未包含評分）
- SKIP 後的 toast 通知（badge 視覺已足夠）
- 多個 threshold 設定（per-persona 差異化）
