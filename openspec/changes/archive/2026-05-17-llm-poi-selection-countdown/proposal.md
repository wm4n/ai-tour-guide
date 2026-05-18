## Why

目前前端 TriggerEngine 自行選出單一 POI 傳給後端，無法利用全部候選清單做智慧挑選，也缺乏對上次解說內容的感知。本次改由後端 LLM 從全部 500m 候選 POI 中選出最合適的地點，並加入 90 秒倒數 badge 作為觸發控制，取代距離觸發邏輯。

## What Changes

- **BREAKING** `POST /narration` request body 改為接受 `candidates: list[POICandidate]` 取代單一 POI 欄位
- 新增 `POICandidate` 和 `PreviousSelection` Pydantic model
- 後端新增 `POISelectorService`：非串流 LLM call，從候選清單選出最適合的 `poi_id`
- `MetaEvent` 新增 `poi_name` 欄位，讓前端知道後端選了哪個 POI
- 前端 `TriggerNotifier` 移除 `TriggerEngine` 距離觸發邏輯，改為 countdown 計時器
- 前端 `NarrationNotifier.narrate()` 改為接受 `List<POI> candidates`，從 MetaEvent 解析選中 POI
- 新增 `CountdownBadge` widget：右下角圓形倒數 badge，90s 到期或點擊立即觸發下一次
- 每次觸發附帶 `previous_selection`（上次 poi_id + 完整腳本），供 LLM 做風格銜接

## Capabilities

### New Capabilities
- `poi-selector`: 後端 LLM POI 選擇服務，從全部 500m 候選中選出最佳 POI，記錄選擇原因
- `countdown-trigger`: 前端倒數觸發機制，取代距離觸發邏輯，含 CountdownBadge UI 元件

### Modified Capabilities
- `narration-stream`: `POST /narration` request body 改為 multi-candidate 格式；MetaEvent 新增 `poi_name`
- `trigger-engine`: 移除距離觸發邏輯，改為 countdown-based 觸發；TriggerNotifier 狀態型別變更

## Impact

**Backend:**
- `backend/src/tour_guide/api/narration.py` — 新 Pydantic models，endpoint 邏輯大改
- `backend/src/tour_guide/services/poi_selector.py` — 新服務（新增）
- `backend/src/tour_guide/services/narration_service.py` — MetaEvent 加 `poi_name`
- `backend/src/tour_guide/main.py` — DI 注入 `POISelectorService`
- `backend/src/tour_guide/log_events.py` — 新增 `POI_SELECTION` event

**Flutter:**
- `flutter_app/lib/shared/backend/backend_client.dart` — 新 `PreviousSelection` model，`narrate()` 簽名改變
- `flutter_app/lib/shared/backend/models/narration_event.dart` — MetaEvent 加 `poiName`
- `flutter_app/lib/features/narration/providers/narration_provider.dart` — `narrate()` 接受 candidates
- `flutter_app/lib/features/narration/providers/trigger_provider.dart` — 全面重寫為 countdown 邏輯
- `flutter_app/lib/features/narration/widgets/countdown_badge.dart` — 新元件（新增）
- `flutter_app/lib/features/map/screens/map_screen.dart` — 加入 `CountdownBadge`

**Tests:**
- `backend/tests/unit/test_poi_selector.py` — 新增
- `flutter_app/test/unit/trigger_provider_test.dart` — 更新
