## 1. 簡化 TriggerState

- [x] 1.1 移除 `TriggerState` 的 `isWaitingForDisplacement`、`skipLat`、`skipLon`、`movedMeters` 欄位
- [x] 1.2 移除 `TriggerState.copyWith()` 中對應的參數

## 2. 移除 displacement-wait 相關程式碼

- [x] 2.1 刪除 `TriggerNotifier` 的 `_locationSub` 欄位（`StreamSubscription<Position>? _locationSub`）
- [x] 2.2 刪除 `_handleSkip()` 方法
- [x] 2.3 刪除 `_startDisplacementWatch()` 方法
- [x] 2.4 刪除 `_clearDisplacementWatch()` 方法
- [x] 2.5 從 `ref.onDispose()` 移除 `_locationSub?.cancel()`

## 3. 修改 _startCountdown()

- [x] 3.1 移除 `_locationSub?.cancel(); _locationSub = null;`（_locationSub 欄位已不存在）
- [x] 3.2 移除 `_lastTriggerPosition = null; _lastCandidateIds = {};`（位置追蹤跨周期持久化）

## 4. 修改 _doCandidatesRequest() 的提前返回路徑

- [x] 4.1 `available.isEmpty` 分支：改為呼叫 `_startCountdown(); return;`（原為直接 `return;`）
- [x] 4.2 dedup guard 阻擋分支：改為 `_startCountdown(); return;`（原為直接 `return;`）

## 5. 修改 SkipEvent 處理

- [x] 5.1 在 `narrationProvider` listener 中，將 `_handleSkip()` 呼叫替換為 `_startCountdown()`

## 6. 更新 countdown_badge.dart

- [x] 6.1 移除 `isWaitingForDisplacement` 分支（`if (triggerState.isWaitingForDisplacement) { return _DisplacementBadge(...); }`）
- [x] 6.2 刪除 `_DisplacementBadge` class 及其所有相關程式碼
- [x] 6.3 確認移除 `appSettingsProvider` watch（如果僅 `_DisplacementBadge` 使用的 `skipDisplacementM` 設定則移除）

## 7. 更新單元測試

- [x] 7.1 修改 `'SkipEvent sets isWaitingForDisplacement and clears countdown'` 測試：改為驗證 `isCountingDown == true`（SkipEvent 後重啟倒數）
- [x] 7.2 移除 `'displacement exceeding threshold re-triggers narration'` 測試（displacement-wait 功能已刪除）
- [x] 7.3 新增測試：`available.isEmpty` 時倒數重啟——使用 1 個 POI、1-second countdown，播完（MetaEvent + EndEvent）後 session 已播，確認下一輪 countdown 到期時 `isCountingDown` 再次變 true
- [x] 7.4 新增測試：dedup guard 阻擋時倒數重啟——使用 5 個 POI、1-second countdown，播完第一輪後不移動，確認第二輪 countdown 到期時因 Jaccard ≥ 0.8 被阻擋並重啟倒數（`isCountingDown == true`）

## 8. 驗證

- [x] 8.1 執行 `flutter test flutter_app/test/unit/trigger_provider_test.dart` 確認所有測試通過
- [x] 8.2 確認編譯無錯誤：`flutter analyze flutter_app/lib/features/narration/`
