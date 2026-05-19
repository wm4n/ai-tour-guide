# Dedup Guard Post-Narration Fix

**日期**：2026-05-19
**狀態**：設計完成，待實作

---

## 問題

`TriggerNotifier._doCandidatesRequest()` 中的 dedup guard 比較「當前可用候選清單」與「上次送出時的清單（`_lastCandidateIds`）」的 Jaccard 相似度，若使用者沒有移動（< 30m）且 Jaccard ≥ 0.8，則跳過本次 LLM 請求。

**漏洞**：後端 LLM 從 a b c d e 五個景點中選了 b 播放後，b 加入 `_sessionPlayedIds` 並從下次的 available 清單移除。但 `_lastCandidateIds` 仍為 `{a,b,c,d,e}`，導致：

```
available      = {a,c,d,e}
_lastCandidateIds = {a,b,c,d,e}
Jaccard = 4/5 = 0.8 >= 0.8  →  誤判為「沒有變化」→ SKIP
```

剩餘四個可能值得說明的景點（a、c、d、e）因此永遠不會被處理。

---

## 設計

### 修改位置

`flutter_app/lib/features/narration/providers/trigger_provider.dart`

`narrationProvider` listener 中，當後端選定景點開始播放時（`prev.currentPoi == null && next.currentPoi != null`）：

```dart
// 修改前
if (prev?.currentPoi == null && next.currentPoi != null) {
  _sessionPlayedIds.add(next.currentPoi!.id);
  _hasEverFired = true;
}

// 修改後
if (prev?.currentPoi == null && next.currentPoi != null) {
  _sessionPlayedIds.add(next.currentPoi!.id);
  _hasEverFired = true;
  _lastCandidateIds = {};  // 播完後讓 dedup guard 失效，下次倒數結束可重送
}
```

### 語意說明

`_lastCandidateIds` 的用意是「若候選清單與上次幾乎相同，且使用者未移動，則不重複發送相同請求」。但如果後端剛剛播了一個景點，候選狀態已實質改變（consumed one candidate），dedup guard 不應阻擋下一輪。清空 `_lastCandidateIds` 讓 guard 在下次判斷時認為「沒有歷史比較基準」，直接送出請求。

### 行為矩陣

| 情境 | `_lastCandidateIds` 的變化 | 下次 dedup 結果 |
|---|---|---|
| 後端選了景點，播完 | 清空 `{}` | guard 不啟動 → 正常送出 ✓ |
| 後端返回 SKIP | 不變（維持上次清單） | Jaccard ≥ 0.8 → 繼續 SKIP ✓ |
| 使用者移動 > 30m | 不影響（moved 判斷先通過） | 正常送出 ✓ |
| 使用者手動 skipCountdown() | 已有 `_lastCandidateIds = {}` | 正常送出 ✓ |

### 不變動的部分

- Jaccard 門檻（0.8）不調整
- 移動距離門檻（30m）不調整
- 後端 SKIP 路徑的 dedup 行為不變
- `_sessionPlayedIds` / 24 小時 cooldown 邏輯不變

---

## 測試策略

在現有 trigger_provider 測試套件中新增一個情境：

**Test case：播完景點後倒數結束應送出第二次請求**

1. 初始：5 個 POI（a b c d e），使用者未移動
2. 第一次 `_doCandidatesRequest()` 送出，`_lastCandidateIds` = `{a,b,c,d,e}`
3. 模擬後端選中 b → `narrationProvider` 發出 `currentPoi = b`
4. 驗證 `_lastCandidateIds` 已清空
5. 倒數結束，`_doCandidatesRequest()` 再次呼叫
6. 驗證：narrate() 被呼叫（candidates = {a,c,d,e}），而非進入 `_startCountdown()` 的 SKIP 路徑

---

## 影響範圍

- 異動檔案：`trigger_provider.dart`（1 行）
- 新增測試：`trigger_provider_test.dart`（1 個新 test case）
- 後端無需改動
