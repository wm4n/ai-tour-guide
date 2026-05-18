## Context

目前 Flutter 前端的 `TriggerEngine` 負責從附近 POI 中挑選一個傳給後端 `/narration` endpoint，後端直接對該 POI 生成解說。這個架構有兩個根本限制：

1. **選擇品質差**：前端只能用簡單的距離排序選 POI，無法考慮 Wikipedia 資料豐富度、主題多樣性、或上次說了什麼。
2. **缺乏節奏控制**：`TriggerEngine` 基於距離觸發，實際使用時容易在同一區域反覆觸發，也沒有明顯的 UI 提示下次觸發時間。

本次設計解決這兩個問題：後端 LLM 選 POI，前端 countdown badge 控制觸發節奏。

**現有架構關係：**
- `POIProvider` 維護 500m 候選清單（不變）
- `TriggerNotifier` 目前用 `TriggerEngine` 距離評估觸發 narration（全面替換）
- `NarrationNotifier` 接受單一 POI 送出請求（改為接受 candidates list）
- `BackendClient.narrate()` 送出單一 POI 格式（改為 multi-candidate）
- `/narration` endpoint 接受單一 POI context（改為 candidates list，加入 selection LLM）

---

## Goals / Non-Goals

**Goals:**
- 後端 LLM 從前端傳來的全部候選 POI 中智慧選出最適合的一個
- MetaEvent 回傳 `poi_name`，讓前端可正確標記已播放的 POI
- Narration 結束後右下角出現 90 秒倒數 badge，到期或點擊立即觸發下一次
- 每次請求附帶上次選中的 POI ID、名稱與完整腳本，讓 LLM 做風格銜接
- 前端依然負責 session 去重和 24h cooldown 過濾，過濾後的 candidates 送後端

**Non-Goals:**
- 後端 cache 機制不改（key 仍為 `poi_id|persona|lang|length`）
- 24h cooldown 和 session 去重邏輯不動（留在前端 TriggerNotifier）
- 手動點擊地圖 POI 觸發 narration 的路徑不變
- 多語言 countdown UI 本地化（「下一個」硬編碼中文）
- `POIProvider` 500m 半徑邏輯不變

---

## Decisions

### D1：POI 選擇邏輯放後端（LLM），不放前端

**選擇**：在後端新增 `POISelectorService`，非串流 LLM call，從候選清單選出 `poi_id`，再串接現有 narration LLM。

**替代方案考慮**：
- 前端加更複雜評分（wiki 有無 × 距離 × 上次主題）：實作複雜且難以迭代，每次改規則都要更新 app。
- 後端單一 LLM call 同時選擇+生成解說：難以對 selection 做獨立測試和 logging，且 prompt 過長會降低解說品質。

**選後端兩步驟的理由**：selection 和 narration 是不同職責，分開後可各自 log、測試、替換模型。

---

### D2：`previous_selection` 永遠帶上，不做 POI 範圍比對

**選擇**：只要 session 內有過 narration，就帶上 `previous_selection`（poi_id、poi_name、script）。

**替代方案考慮**：
- 只有上次 POI 仍在當前 500m 範圍內才帶：降低複雜性但損失風格銜接能力。
- 帶多次歷史（rolling window）：API payload 增大、實作複雜，MVP 不需要。

**選擇理由**：即使移動到新區域，上次 script 有助於 LLM 避免重複開場詞和主題，前端邏輯保持 O(1)。

---

### D3：Countdown 由前端 `TriggerNotifier` 管理，不放 backend

**選擇**：`TriggerNotifier` 在 narration 結束時啟動 `Timer.periodic(1s)`，countdown 狀態透過 Riverpod 通知 UI。

**替代方案考慮**：
- Backend 控制重觸發（例如 SSE keep-alive + server-push）：與現有 SSE 架構不兼容，過度工程化。
- 前端用 `Future.delayed(90s)` 不做每秒更新：無法顯示倒數數字，UX 差。

**選擇理由**：Timer.periodic 是 Dart 原生機制，狀態管理直覺，badge UI 可即時反映剩餘秒數。

---

### D4：NarrationNotifier 累積 `scriptBuffer`

**選擇**：`NarrationState` 新增 `scriptBuffer` 欄位，每次 `TextEvent` chunk 累加，narration 完成後由 `TriggerNotifier` 取出作為 `previous_selection.script`。

**替代方案考慮**：
- 後端直接在 EndEvent 裡回傳完整腳本：需要後端額外存儲腳本，破壞 SSE 無狀態特性。
- 前端 TriggerNotifier 直接監聽 TextEvent stream：打破關注點分離，TriggerNotifier 不應知道 SSE 細節。

**選擇理由**：NarrationNotifier 本來就收到所有 TextEvent，累積 buffer 是最自然的位置，TriggerNotifier 只需讀取 `state.scriptBuffer` 即可。

---

## Risks / Trade-offs

**[Performance] Selection LLM call 增加 latency** → Mitigation：使用低 temperature（0.1）和 max_tokens=64 的輕量 call，Gemini Flash 預估 <500ms；不影響 narration 串流開始時間感知（使用者先看到 loading 狀態）。

**[UX] 90s 倒數對某些場景太長或太短** → Mitigation：`_countdownDuration` 為常數，MVP 先固定 90s，未來可從後端 AppConfig 或 session 設定讀取。

**[Edge Case] candidates 全被過濾（session + cooldown）後 available 為空** → Mitigation：`_doCandidatesRequest()` 在 available.isEmpty 時直接 return，不啟動 countdown（避免無限觸發空請求）。

**[Correctness] MetaEvent poi_id 不在 candidates 列表中** → Mitigation：`NarrationNotifier._handle()` 用 `firstWhere(orElse:)` fallback 到 candidates.first，確保不會 throw。

**[Testing] CountdownBadge 動畫在測試環境需要 fake timer** → Mitigation：unit tests 使用 `Duration(milliseconds: 50)` delay 驗證狀態轉換，不測試 widget 動畫本身；widget test 留待後續補充。

---

## Migration Plan

1. **後端先行**：先部署含 `POISelectorService` 的後端（Task 1-4）。新 endpoint 接受 `candidates` list；舊格式的前端請求在部署期間若有 validation error，Flutter 端會顯示 error state（可接受的短暫降級）。
2. **Flutter 同步更新**：Tasks 5-10 在同一 PR 中合並，確保前後端同時切換。
3. **Rollback**：後端可快速回滾 `narration.py` 到前一版本（保留單一 POI 格式）；Flutter 端若 API 失敗會停在 error 狀態，不會 crash。

---

## Open Questions

- `previous_selection.script` 長度是否需要截斷？目前實作截到 400 chars（在 `POISelectorService` 的 prompt 中），但若前端 `scriptBuffer` 非常長（長篇解說），是否應在前端就截？→ MVP 先前端不截，後端 prompt 截斷 400 chars。
- Countdown 時長未來是否應由後端下發（例如 `EndEvent` 附帶 `next_trigger_s`）？→ MVP 先硬編碼 90s，未來迭代時考慮。
- `TriggerNotifier` 的 `appLifecycleStateProvider` 目前在 test fixture 中需要額外 override，是否有更優雅的注入方式？→ 留待 refactor。
