## Why

目前 `POISelectorService` 收到候選 POI 清單後必定選出一個來旁白，即使所有候選都是不值得說明的瑣碎景點（地圖看板、導覽牌、公車站牌等），仍會觸發 LLM 旁白並浪費 token；旁白結束後倒數計時繼續，導致瑣碎地點附近無限觸發旁白。

## What Changes

- **Backend**：`POISelectorService.select()` 回傳型別改為 `str | None`，LLM 可回覆 `SKIP` 表示所有候選皆為瑣碎景點
- **Backend**：narration endpoint 當 `select()` 回傳 `None` 時，串流單一 `skip` SSE 事件後關閉連線
- **Flutter**：新增 `SkipEvent` narration event 類型，SSE 解析器支援 `event: skip`
- **Flutter**：新增 `AppSettings` 模型與 `appSettingsProvider`，以 SharedPreferences 持久化「位移門檻」與「倒數秒數」設定
- **Flutter**：`TriggerProvider` 收到 skip 後進入「等待位移」模式，待用戶移動超過門檻距離後重觸發旁白
- **Flutter**：`CountdownBadge` 新增位移等待狀態（灰底步行圖示，顯示 `x.x / 1.5km` 進度）
- **Flutter**：新增 `SettingsScreen`，讓用戶以 slider 調整旁白間隔與位移門檻

## Capabilities

### New Capabilities
- `poi-importance-filter`: LLM 判斷候選 POI 皆為瑣碎時回傳 SKIP 信號；backend 串流 skip SSE；Flutter 進入位移等待模式，直到用戶移動足夠距離才重觸發旁白
- `app-settings`: 用戶可調整旁白倒數秒數與 skip 後位移門檻，設定以 SharedPreferences 持久化，並從 SettingsScreen 入口存取

### Modified Capabilities
- `poi-selector`: `select()` 回傳型別從 `str` 改為 `str | None`，新增 SKIP prompt 規則
- `narration-stream`: endpoint 新增 skip 事件分支；Flutter SSE 解析器新增 `skip` event type
- `trigger-engine`: `TriggerState` 新增 `isWaitingForDisplacement` 等位移相關欄位；`TriggerNotifier` 新增 `_handleSkip()` 與 `_startDisplacementWatch()` 邏輯；倒數秒數改由 `appSettingsProvider` 動態讀取

## Impact

- **Backend 檔案**：`backend/src/tour_guide/services/poi_selector.py`、`backend/src/tour_guide/api/narration.py`、`backend/src/tour_guide/log_events.py`
- **Flutter 檔案**：`narration_event.dart`、`backend_client.dart`、`trigger_provider.dart`、`narration_provider.dart`、`countdown_badge.dart`、`map_screen.dart`
- **Flutter 新增檔案**：`shared/settings/app_settings.dart`、`shared/settings/settings_provider.dart`、`features/settings/settings_screen.dart`
- **新增依賴**：`shared_preferences: ^2.3.2`
- **測試**：backend unit tests (`test_poi_selector.py`, `test_narration_skip.py`)；Flutter unit tests (`settings_provider_test.dart`, `trigger_provider_test.dart` 擴充)
