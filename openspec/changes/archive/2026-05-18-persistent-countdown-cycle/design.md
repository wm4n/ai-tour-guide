## Context

Trigger engine 目前在三種情況下會靜默卡死：

1. **`available.isEmpty`**：所有候選 POI 都已播放或在冷卻期，`_doCandidatesRequest()` 直接 `return`，不觸發任何後續動作。
2. **Dedup guard 阻擋**：用戶未移動且 Jaccard ≥ 0.8，同樣直接 `return`。
3. **SkipEvent**：LLM 判定 POI 不值得旁白，`_handleSkip()` 進入 displacement-wait 模式——等待用戶移動超過 `skipDisplacementM`（預設 500m）才重新觸發。

Displacement-wait 模式在城市旅遊場景下幾乎永遠不會滿足（500m 門檻過高），且引入了額外的 `_locationSub` 訂閱和 `TriggerState` 欄位（`isWaitingForDisplacement`、`skipLat`、`skipLon`、`movedMeters`），增加狀態複雜度。

核心問題：**倒數計時是系統的 heartbeat，任何路徑都應該讓它繼續跳動。**

## Goals / Non-Goals

**Goals:**
- 所有非旁白結果（`available.isEmpty`、dedup guard 阻擋、SkipEvent）皆呼叫 `_startCountdown()`，讓倒數持續循環
- 移除 displacement-wait 模式及所有相關程式碼（`_handleSkip()`、`_startDisplacementWatch()`、`_clearDisplacementWatch()`、`_locationSub`）
- 簡化 `TriggerState`：移除 `isWaitingForDisplacement`、`skipLat`、`skipLon`、`movedMeters`
- `_startCountdown()` 不再重置 `_lastTriggerPosition` 與 `_lastCandidateIds`，讓 dedup guard 在跨周期持續有效
- 僅 `skipCountdown()`（用戶主動點擊）才重置位置追蹤，視為明確希望立即觸發
- 移除 `countdown_badge.dart` 的 displacement UI（`_DisplacementBadge`）

**Non-Goals:**
- 不修改 dedup guard 的判斷邏輯（30m 移動門檻與 Jaccard ≥ 0.8 保持不變）
- 不修改 narration 流程（`narrationProvider`、後端 API）
- 不修改冷卻期邏輯（24 小時 DB cooldown）
- 不調整 `countdownSeconds` 設定值

## Decisions

### 決策 1：SkipEvent → `_startCountdown()` 而非 displacement-wait

**選擇**：收到 SkipEvent 時呼叫 `_startCountdown()`。

**理由**：
- Displacement-wait 在城市場景中幾乎永遠不滿足（500m 門檻），導致系統卡死的體感比 SkipEvent 本身更嚴重。
- `_startCountdown()` 讓系統在固定時間後自動重試，行為可預測。
- 移除 displacement-wait 可刪除大量狀態管理程式碼（`_locationSub`、4 個 TriggerState 欄位、3 個方法）。

**替代方案考量**：保留 displacement-wait 但降低門檻 → 仍需維護複雜狀態，且門檻值難以調校。

### 決策 2：`_startCountdown()` 不重置位置追蹤

**選擇**：從 `_startCountdown()` 移除 `_lastTriggerPosition = null; _lastCandidateIds = {};`。

**理由**：
- 原本重置是為了讓 countdown 到期後可以順利通過 dedup guard。但這樣每次倒數都強制觸發 narration，破壞 dedup guard 的防重複意義。
- 保留位置追蹤讓 dedup guard 持續有效：用戶沒移動且 POI 不變時，連續幾輪 countdown 都會被 guard 阻擋，然後 **guard 阻擋 → `_startCountdown()`** 形成 heartbeat 循環，直到用戶移動或 POI 改變。
- `skipCountdown()`（用戶主動操作）仍重置追蹤，確保用戶點擊後能立即播放。

**替代方案考量**：在 `_startCountdown()` 保留重置 → 每輪 countdown 必定觸發 narration，即使用戶完全靜止且 POI 相同，與 dedup guard 的設計目的衝突。

### 決策 3：`available.isEmpty` → `_startCountdown()` 而非靜默退出

**選擇**：所有 POI 都已播放或在冷卻期時，呼叫 `_startCountdown()` 繼續等待。

**理由**：
- 冷卻期（24 小時）會隨時間到期。若系統靜默卡死，用戶無法得知系統還在運作。
- Heartbeat 模式確保用戶移動到新區域時（`_latestPois` 更新），下一輪 countdown 可以發現新 POI。
- 日誌仍記錄 `reason: no_candidates_available`，便於問題追蹤。

## Risks / Trade-offs

- **[風險] 頻繁的 `_startCountdown()` 呼叫**：每次 guard 阻擋都重啟 countdown，形成 heartbeat 循環。但 `countdownSeconds`（預設 90 秒）確保不會頻繁呼叫後端。→ **緩解**：dedup guard 在 countdown 到期後也會攔截，不會真正打到後端。
- **[風險] 用戶感知倒數但沒有旁白**：倒數歸零後被 dedup guard 攔截，又重啟倒數，用戶會看到倒數不斷循環。→ **緩解**：此行為已優於當前靜默卡死；未來可加 UI 提示「已播完附近景點」，但不在本次範圍。
- **[Trade-off] 移除 displacement-wait UI**：`_DisplacementBadge` 刪除後，LLM SkipEvent 的處理對用戶完全透明（倒數繼續）。→ 接受，因 displacement-wait 本身幾乎不可觸及，UI 無意義。

## Migration Plan

1. 更新 `TriggerState`：移除 4 個欄位與對應的 `copyWith` 參數
2. 更新 `TriggerNotifier`：
   - 刪除 `_locationSub` 欄位
   - 修改 `_startCountdown()`：移除重置位置追蹤的兩行
   - 修改 `_doCandidatesRequest()`：`available.isEmpty` 和 dedup guard 阻擋改呼叫 `_startCountdown()`
   - 修改 `narrationProvider` listener：SkipEvent 改呼叫 `_startCountdown()`
   - 刪除 `_handleSkip()`、`_startDisplacementWatch()`、`_clearDisplacementWatch()`
   - 更新 `ref.onDispose()`：移除 `_locationSub?.cancel()`
3. 更新 `countdown_badge.dart`：移除 `isWaitingForDisplacement` 分支和 `_DisplacementBadge` class
4. 更新 `trigger_provider_test.dart`：修改和新增測試案例

**回滾策略**：變更範圍限於 Flutter app，無後端修改。若需回滾，git revert 即可。

## Open Questions

無。設計方向明確，所有邊界情況已在 spec 中涵蓋。
