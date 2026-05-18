## Why

Trigger engine 目前有三種卡死情況：當所有景點皆已播放（`available.isEmpty`）、dedup guard 阻擋（用戶未移動且 Jaccard ≥ 0.8）、或 LLM 回傳 SkipEvent 時，系統不重啟倒數計時，導致旁白永遠不會再觸發。這些邊界情況讓旅途中途系統靜默卡死，嚴重影響使用者體驗。

## What Changes

- **移除 displacement-wait 模式**：刪除 `_handleSkip()`、`_startDisplacementWatch()`、`_clearDisplacementWatch()` 方法，以及 `_locationSub` 訂閱。SkipEvent 不再進入位移等待模式，改為重啟倒數計時。
- **任何非旁白結果皆重啟倒數**：`_doCandidatesRequest()` 的所有提前返回路徑（`available.isEmpty`、dedup guard 阻擋）都改為呼叫 `_startCountdown()`，讓倒數計時成為系統的心跳。
- **`_startCountdown()` 不再重置位置追蹤**：移除 `_startCountdown()` 中對 `_lastTriggerPosition = null` 與 `_lastCandidateIds = {}` 的重置，使位置狀態跨周期持久化，確保 dedup guard 持續有效。
- **僅 `skipCountdown()` 重置位置**：用戶主動點擊 CountdownBadge 時才重置位置追蹤，視為用戶明確希望立即觸發旁白。
- **簡化 `TriggerState`**：移除 `isWaitingForDisplacement`、`skipLat`、`skipLon`、`movedMeters` 欄位，僅保留 `isCountingDown` 與 `countdownRemaining`。
- **更新 CountdownBadge**：移除任何與 `isWaitingForDisplacement` 相關的 UI 邏輯。
- **更新單元測試**：移除 displacement-wait 相關測試案例，新增三種卡死情況的重啟倒數測試。

## Capabilities

### New Capabilities

- `persistent-countdown-cycle`: 倒數計時作為系統 heartbeat——任何非旁白結果（`available.isEmpty`、dedup guard 阻擋、SkipEvent）皆重啟倒數，確保系統永不卡死。

### Modified Capabilities

- `trigger-engine`: 移除 displacement-wait 模式，改變 `_startCountdown()` 的位置追蹤重置行為，以及所有提前返回路徑的行為（改為重啟倒數而非靜默退出）。

## Impact

- **`flutter_app/lib/features/narration/providers/trigger_provider.dart`**：主要修改目標，移除 displacement-wait 相關程式碼，修改 `_startCountdown()` 與 `_doCandidatesRequest()` 的行為邏輯。
- **`flutter_app/lib/features/narration/widgets/countdown_badge.dart`**：移除 `isWaitingForDisplacement` 相關 UI 顯示邏輯。
- **`flutter_app/test/unit/trigger_provider_test.dart`**：更新測試以反映新行為，移除舊測試，新增三種邊界情況的測試。
- **不影響後端 API**、不影響其他 provider、不影響 narration 流程本身。
