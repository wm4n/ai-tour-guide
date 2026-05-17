# LLM POI Selection + Countdown Trigger Design

**Date:** 2026-05-17
**Status:** Approved

## Overview

目前前端透過 TriggerEngine 自行選出一個 POI 傳給後端播放解說。本次改為由後端 LLM 從所有 500m 候選 POI 中選出最合適的，並加入 YouTube 風格的倒數 UI 控制觸發間隔。

---

## Goals

1. 後端 LLM 從 500m 範圍全部候選 POI 中選出最適合講解的地點
2. 後端回傳選中的 POI，前端用現有機制排除（session set + 24h cooldown）
3. Narration 結束後顯示右下角倒數 badge（90s），到期自動觸發下一次
4. 用戶可點擊倒數 badge 立即觸發（測試友善）
5. 每次送出附帶上次選中的 POI 和完整腳本，讓 LLM 做風格銜接

---

## Architecture

### 整體資料流

```
[位置更新]
     ↓
 POI Provider — 維護 500m 候選清單（不變）
     ↓
 Trigger Provider
   - 移除 TriggerEngine 距離 trigger 邏輯
   - 唯一觸發點：Countdown 到期 or 用戶點擊 badge
     ↓
 NarrationRequest（全部 500m POI candidates + previous_selection）
     ↓
 後端：Selection LLM → 選出 poi_id → Narration LLM 串流
     ↓
 MetaEvent 回傳選中的 poi_id + poi_name
     ↓
 前端：標記為已播放（現有 session set + DB cooldown 機制不變）
     ↓
 播完 → 啟動 Countdown (90s) → 右下角 badge 顯示倒數
     ↓
 到期 or 點擊 → 重新送出 request
```

---

## API Design

### Request — `POST /narration`

現有 endpoint，修改 request body：

```python
class NarrationRequest(BaseModel):
    candidates: list[POICandidate]          # 全部 500m POI
    persona: str
    lang: str
    length: str = "medium"
    force_regenerate: bool = False
    previous_selection: PreviousSelection | None = None

class POICandidate(BaseModel):
    poi_id: str
    poi_name: str
    poi_lat: float
    poi_lon: float
    distance_m: float                       # 用戶目前到此 POI 的距離
    poi_tags: dict[str, str]
    wiki_title: str | None
    wiki_extract: str | None

class PreviousSelection(BaseModel):
    poi_id: str
    poi_name: str
    script: str                             # 上次完整腳本
```

### Response — SSE（格式不變，MetaEvent 加欄位）

```json
{
  "event": "meta",
  "data": {
    "poi_id": "node/123456",
    "poi_name": "故宮博物院",
    "cache_hit": false,
    "estimated_duration_s": 45
  }
}
```

MetaEvent 新增 `poi_name`，前端用於標記已播放及顯示。

### 後端內部兩步驟

1. **Selection call**（非串流）：LLM 從 candidates 選出最合適的 POI，回傳 `poi_id`
2. **Narration call**（串流，現有邏輯）：針對選中 POI 產出腳本，透過 SSE 回傳

Selection prompt 應包含：
- 候選清單（poi_name、distance_m、wiki 摘要有無）
- previous_selection（若存在）：告知 LLM 上次選了什麼、說了什麼
- 優先選距離近、有 wiki 資料、與上次主題不重複的 POI

---

## Frontend Design

### Trigger Provider 變更

```dart
// 移除
TriggerEngine.evaluate(...)

// 新增狀態
DateTime? _cooldownUntil;
POI? _lastSelectedPoi;
String? _lastScript;

// 觸發流程
// 1. Narration 結束 → _cooldownUntil = now + 90s → 啟動 Timer
// 2. Timer 每秒 notify UI
// 3. 到期 → _sendCandidates()
// 4. 用戶點擊 badge → 取消 timer → 立即 _sendCandidates()

void _sendCandidates() {
  final candidates = _buildCandidates(currentPois, userPosition);
  final previous = _lastSelectedPoi != null
      ? PreviousSelection(poi: _lastSelectedPoi!, script: _lastScript!)
      : null;
  narrationProvider.narrate(candidates: candidates, previous: previous);
}
```

### Narration Provider 變更

- `narrate()` 改為接受 `candidates` 列表而非單一 POI
- 解析 MetaEvent 取得 `poi_id` + `poi_name`
- 將 `poi_id` 傳回 trigger_provider 作為 `_lastSelectedPoi`
- 串流結束後通知 trigger_provider 啟動 countdown

### Backend Client 變更

- `postNarration()` 改為接受 `List<POICandidate>` + `PreviousSelection?`
- 回傳型別不變（SSE stream）

### Countdown Badge Widget

```
┌──────────────────────────────────┐
│  地圖                            │
│                                  │
│                    ┌──────────┐  │
│                    │  ⟳  42s │  │
│                    │  下一個  │  │
│                    └──────────┘  │
└──────────────────────────────────┘
```

- 圓形 CircularProgressIndicator（倒數進度）
- 顯示剩餘秒數 + 「下一個」文字
- 點擊立即觸發
- 僅在 cooldown 期間顯示；narration 播放中隱藏

---

## `previous_selection` 傳送規則

**規則**：只要 session 內有過 narration 播放記錄，就帶上 `previous_selection`，不做 POI 清單比對。

理由：
- LLM 可從 candidates 判斷上次 POI 是否仍在範圍內
- 即使到新區域，帶舊 context 有助於 LLM 做風格銜接（避免重複開場）
- 前端邏輯保持簡單

---

## Excluded from Scope

- 後端 cache 機制不變（key 仍為 `poi_id|persona|lang|length`）
- 24h cooldown 和 session 去重邏輯不變
- 手動點擊 map POI 觸發 narration 的路徑不變

---

## Testing Notes

- 點擊右下角 countdown badge 可立即觸發，方便開發測試
- `force_regenerate: true` 仍可繞過 cache
- Selection LLM call 應加 logging，記錄每次選了哪個 POI 和原因
