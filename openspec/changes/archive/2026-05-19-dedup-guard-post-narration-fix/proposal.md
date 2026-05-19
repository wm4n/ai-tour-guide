## Why

`TriggerNotifier` 的 dedup guard 在後端播放景點後會誤判候選清單「沒有變化」，導致剩餘景點永遠不會被 narrate。根本原因是 `_lastCandidateIds` 在景點播完後沒有被清空，使 Jaccard 相似度計算以「播放前的 5 個 POI」對比「播放後的 4 個 POI」，得到 0.8 的相似度而觸發 SKIP。

## What Changes

- 在 `narrationProvider` listener 偵測到景點開始播放（`prev.currentPoi == null && next.currentPoi != null`）時，立即清空 `_lastCandidateIds = {}`
- 更新既有的「dedup guard blocks」測試，將情境改為後端回傳 `SkipEvent`（原測試情境因修復而語意改變）
- 新增測試：驗證播完景點後倒數結束時能正確發送第二次請求

## Capabilities

### New Capabilities

（無新增 capability）

### Modified Capabilities

- `trigger-engine`：dedup guard 的觸發條件新增例外——當後端剛播放景點時（consumed a candidate），必須清空歷史比較基準，讓下一輪倒數結束後能正常送出 LLM 請求，而非被 Jaccard 相似度誤判阻擋。

## Impact

- **異動檔案**：`flutter_app/lib/features/narration/providers/trigger_provider.dart`（1 行新增）
- **測試異動**：`flutter_app/test/unit/trigger_provider_test.dart`（1 個新 test case；1 個既有 test case 更新）
- **後端**：無需改動
- **其他 provider**：無影響（`_lastCandidateIds` 是 `TriggerNotifier` 的私有欄位）
