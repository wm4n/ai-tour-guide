## Context

`TriggerNotifier` 在 `flutter_app/lib/features/narration/providers/trigger_provider.dart` 中維護一個 dedup guard，用於避免在使用者靜止且候選景點清單未變化時重複送出 LLM 請求。Guard 的判斷依據是 `_lastCandidateIds`（上次送出時的候選 ID 集合）與當前 available 候選清單的 Jaccard 相似度，門檻 ≥ 0.8 時跳過本次請求。

**漏洞**：後端 LLM 從 5 個景點中選了 1 個播放後，該景點加入 `_sessionPlayedIds` 並從下次的 available 清單移除，但 `_lastCandidateIds` 仍保留原本 5 個 ID。導致：
- available = {a,c,d,e}（4 個）
- `_lastCandidateIds` = {a,b,c,d,e}（5 個）
- Jaccard = 4/5 = 0.8 ≥ 0.8 → 誤判為「沒有變化」→ SKIP

剩餘四個可能值得說明的景點因此永遠不會被 narrate。

**相關 stakeholder**：Flutter 前端（`TriggerNotifier`、`NarrationNotifier`）、後端無需改動。

## Goals / Non-Goals

**Goals:**
- 修復 dedup guard 在後端播放景點後誤判導致剩餘景點永遠不被 narrate 的問題
- 維持後端返回 `SkipEvent` 時 dedup guard 正常阻擋的行為不變
- 新增測試覆蓋「播完景點後第二次倒數結束應送出請求」的情境
- 更新語意已改變的既有測試（原先測試的情境現在會觸發修復後的清空邏輯）

**Non-Goals:**
- 調整 Jaccard 相似度門檻（0.8）
- 調整移動距離門檻（30m）
- 修改後端行為
- 影響 `_sessionPlayedIds`、24 小時 cooldown 等其他去重邏輯

## Decisions

**決策 1：清空 `_lastCandidateIds` 而非修改 Jaccard 計算**

選擇在「景點開始播放」事件時清空 `_lastCandidateIds = {}`，而非調整 Jaccard 門檻或修改計算方式。

理由：`_lastCandidateIds` 的語意是「若候選清單與上次幾乎相同，且使用者未移動，則不重複發送相同請求」。後端播了景點代表候選狀態已實質改變（consumed one candidate），dedup guard 不應阻擋下一輪。清空 `_lastCandidateIds` 讓 guard 在下次判斷時認為「沒有歷史比較基準」，直接送出請求，語意最清晰。

替代方案考慮：
- 調整門檻至 0.9 → 治標不治本，後端播了 2/5 個景點後 Jaccard = 3/5 = 0.6 才能避過，且影響其他正常情境
- 從 available 清單計算（扣除已播） → 需修改 Jaccard 計算邏輯，影響範圍更大

**決策 2：在 `narrationProvider` listener 中清空，而非在 `_doCandidatesRequest` 中清空**

修改點在 listener 的 `prev?.currentPoi == null && next.currentPoi != null` 分支（景點開始播放時），與現有的 `_sessionPlayedIds.add()` 和 `_hasEverFired = true` 同一位置。

理由：此處語意對應「後端剛選定景點開始播放」，是最精確的時機點。若在 `_doCandidatesRequest` 中處理，需額外追蹤「上次請求是否有播出景點」，增加狀態複雜度。

**決策 3：更新既有「dedup guard blocks」測試的情境為 SkipEvent**

原有測試使用 `[MetaEvent, EndEvent]`（有景點播放），但修復後這個情境會清空 `_lastCandidateIds`，使 dedup guard 不再阻擋第二次請求，原測試的語意已改變。改用 `[SkipEvent()]` 作為情境，正確反映「後端 SKIP 且 POI 未變時 dedup guard 阻擋」的設計意圖。

## Risks / Trade-offs

**[風險 1] 清空 `_lastCandidateIds` 可能在邊緣情境下導致額外 LLM 請求** → 緩解：只在景點開始播放（`prev.currentPoi == null && next.currentPoi != null`）時清空，後端 SKIP 路徑不觸發。使用者靜止且後端 SKIP 的情境行為不變。此外，`_sessionPlayedIds` 的 24 小時 cooldown 機制仍保護已播過的景點不被重複請求。

**[風險 2] 測試更新可能遺漏其他依賴原有行為的情境** → 緩解：執行完整測試套件確認無回歸；新舊兩個測試都有明確的 `reason` 說明語意，方便未來維護者理解意圖。

**[Trade-off] 一行修改 vs. 語意清晰度**：`_lastCandidateIds = {}` 的影響需讀者理解 dedup guard 的完整邏輯，建議搭配行內注解說明「播完後讓 dedup guard 失效」。

## Migration Plan

1. 修改 `trigger_provider.dart`（1 行新增）
2. 新增測試 case（TDD Red → Green）
3. 更新既有測試（語意修正）
4. 執行完整測試套件確認無回歸
5. 提交單一 commit

無需後端部署、資料遷移或 rollback 計劃（純前端邏輯，可透過版本回退處理）。

## Open Questions

（無未解決問題）
