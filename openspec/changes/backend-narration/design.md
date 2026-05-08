## Context

Plan A 的目標是在 Flutter App 開發（Plan B）開始之前，獨立交付一個可本機執行的 Python/FastAPI 後端，驗證「給座標出旁白」的核心 streaming pipeline 可行性。

目前 `backend/` 目錄不存在；本 change 從零建立整個後端專案。設計參考來源：
- `docs/superpowers/specs/2026-05-08-ai-tour-guide-design.md`（§3、§4.2、§6、§7.2、§8、§10.2）
- `docs/superpowers/plans/2026-05-08-plan-a-backend-mvp.md`（29 個 TDD 任務）

適用範圍：v1 自用、單一 persona（`history_uncle`，zh-TW）、無登入、無 Cloud Run 部署（Plan F 才加）。

## Goals / Non-Goals

**Goals:**
- 交付三個 HTTP endpoint：`GET /poi/nearby`、`POST /narration`（SSE）、`GET /health`
- 實作五個核心模組：`POIService`、`NarrationService`、`SentenceSplitter`（純函式）、`PromptBuilder`（純函式）、`ConfidenceClassifier`（純函式）
- Provider 抽象介面（`LlmProvider` / `TtsProvider`）+ LiteLLM / Gemini 實作 + Fake 測試替身
- 外部 client 封裝：`OverpassClient`（Overpass API）、`WikipediaClient`
- 兩層快取：`POICache`（TTL 30 天）、`NarrationCache`（key：poi+persona+lang+length）
- Persona 資源檔系統：YAML 定義 `history_uncle`（zh-TW）
- 完整 TDD 測試套件（unit / integration / smoke 三層），integration tests 完全離線（使用 fake providers）

**Non-Goals:**
- `/qa` endpoint 與 STT（Plan D）
- 其餘 4 個 persona 與多語（Plan C）
- 食家 persona + Google Places（Plan E）
- Cloud Run 部署 + `X-API-Key` 保護（Plan F）
- Flutter App（Plan B）
- 完整字幕時間對齊、POI 圖片（v1 明確排除）

## Decisions

### 1. 為何選 LiteLLM 作為 LLM 抽象層

**決策**：用 LiteLLM 包裝 Gemini，而非直接用 `google-genai` SDK 呼叫 LLM。

**理由**：
- LiteLLM 提供 OpenAI 相容介面，換 provider（Claude、OpenAI）只需改 model 字串，不改架構
- 不抹平 prompt caching（各 provider 的 cache 特性仍可利用）
- `google-genai` SDK 直接用於 TTS（LiteLLM 不覆蓋 TTS），兩者並存不衝突

**替代方案考慮**：直接用 `google-genai` 呼叫 Gemini chat → 被否決，因為換 provider 就要改業務邏輯。

**已知風險**：LiteLLM 對 Gemini streaming API mapping 可能不穩定 → 退路是直接回退 `google-genai` SDK（介面已抽象，只需換 adapter）。

---

### 2. 後端完全無狀態

**決策**：後端不儲存任何 user state；所有 cache 都是「可被清掉、清掉只是變慢」。

**理由**：
- v1 自用、無登入 → 不需要 user context
- Cloud Run scale-to-zero + 多實例 → 無狀態是唯一合理選擇
- 裝置端 SQLite（drift）負責 cooldown / history / session 管理

**Trade-off**：`NarrationCache` 落在容器 `/tmp/`，Cloud Run 冷啟動後快取消失 → v1 可接受（自用配額夠）；v2 升 GCS bucket。

---

### 3. 三層 Provider 抽象

**決策**：`LlmProvider`、`TtsProvider`、`SttProvider` 各有獨立 interface，Plan A 只實作前兩個（STT 在 Plan D）。

**介面契約**：
```python
class LlmProvider(Protocol):
    async def chat_stream(self, messages: list[Message], opts: LlmOpts) -> AsyncIterator[str]: ...

class TtsProvider(Protocol):
    async def synthesize(self, text: str, voice_id: str, opts: TtsOpts) -> AsyncIterator[bytes]: ...
```

每個 provider 對應一個 Fake 測試替身（`FakeLlmProvider`、`FakeTtsProvider`），讓所有上層測試完全離線。

---

### 4. 串流 Pipeline 設計

**決策**：LLM streaming → `SentenceSplitter`（邊收邊切）→ TTS 逐句合成 → 交錯 SSE 推送 `text` 和 `audio` event。

**理由**：首字延遲 ~2 秒是體驗成敗關鍵；等 LLM 全部生成完才 TTS 會有 30-60 秒延遲。

**實作重點**：
- `SentenceSplitter` 是純函式，支援中英文混合標點（。！？.!?）
- 後端邊串流邊累積完整音訊，串完後寫入 `NarrationCache`
- SSE event 類型：`meta` → `text` + `audio`（交錯）→ `end` 或 `error`

---

### 5. 兩層 Cache 設計

**POICache**（POI 背景資料）：
- 兩層 key：區域層（lat/lon 0.001 grid ~100m，TTL 30 天）+ POI 層（poi_id，TTL 30 天）
- 存 `/tmp/tour_guide_cache/`，上限 100 MB，簡單 LRU

**NarrationCache**（已合成音訊）：
- Key：`{poi_id}|{persona}|{lang}|{length}`
- 存 `/tmp/tour_guide_narration_cache/`，上限 500 MB
- 命中時直接 stream 既有音訊，大幅降低 Gemini 配額消耗

---

### 6. Persona YAML 系統

**決策**：每個 persona 是獨立 YAML（`prompts/personas/{id}.yaml`），`PromptBuilder` 從 YAML 組裝 prompt，persona 調整不需改程式碼。

**Plan A 範圍**：僅 `history_uncle.yaml`（zh-TW），包含 `system_prompt`、`narration_template`、`voice`、`style_profile`、`confidence_labels`。

---

### 7. 為何 v1 無 auth（僅 `X-API-Key` 輕量保護）

**決策**：Plan A 本機開發階段完全無 auth；Cloud Run 部署時（Plan F）才加 `X-API-Key` header。

**理由**：v1 自用、本機跑，加 auth 增加複雜度但無安全收益。`X-API-Key` 只是防止 URL 外流後被陌生人刷 Gemini 配額。

---

### 8. 技術棧選擇

| 用途 | 套件 | 理由 |
|---|---|---|
| Web framework | FastAPI | async 原生、SSE 支援、pydantic 整合 |
| SSE | sse-starlette | FastAPI 生態最成熟 |
| LLM 抽象 | litellm | provider 無關換字串即換廠 |
| Gemini SDK | google-genai | 官方 TTS 支援 |
| HTTP client | httpx | async、respx 測試替身完整 |
| 設定 | pydantic-settings | 型別安全的環境變數 |
| 測試 | pytest + pytest-asyncio + respx + freezegun | async 測試 + HTTP mock + 時間控制 |

## Risks / Trade-offs

**[風險 1] LiteLLM × Gemini streaming 相容性** → 緩解：保留直接切回 `google-genai` SDK 的 adapter 路徑；介面已抽象，切換只改 `LiteLLMAdapter` 實作。

**[風險 2] Cloud Run `/tmp` cache 冷啟動清空** → 緩解：v1 自用 Gemini free tier 配額足；v2 升 GCS bucket（NarrationCache key 設計相容）。

**[風險 3] Overpass 公共伺服器限流** → 緩解：`OverpassClient` 內建 retry + backoff；v1 自用流量低不需自架 mirror。

**[風險 4] `SentenceSplitter` 中英混合邊界** → 緩解：純函式最易單測；先寫 test cases 再實作（TDD）。

**[Trade-off] 音訊 base64 in SSE** → SSE 規範限 text-only；base64 多 33% 體積換簡化解析（v1 acceptable）。

## Migration Plan

1. 建立 `backend/` 目錄結構（Task 1）
2. 依 TDD 順序實作純函式模組（Tasks 3-8）
3. 實作 Provider 介面與 Fake（Tasks 9-10）
4. 組裝 NarrationService（Task 11）
5. 實作外部 clients（Tasks 12-13）+ POI filter（Task 14）+ POIService（Task 15）
6. 實作 cache 層（Tasks 21-23）
7. 實作真實 Provider adapters（Tasks 24-25）
8. 完成 API layer + DI wiring（Tasks 16-20, 26）
9. 全面測試 + lint（Tasks 27-29）

**Rollback**：本 change 全新建立 `backend/`，不改動任何現有檔案，rollback 即刪除 `backend/` 目錄。

## Open Questions

- Gemini 2.5 Flash TTS 30 個 voice 的中英文表現是否能充分區分 5 個 persona（Plan C 才驗證）
- LiteLLM 對 Gemini streaming 的 mapping 穩定性 → Task 24 實作時需手動驗證
- Overpass 公共伺服器在自用流量下的實際限流閾值（Task 13 smoke test 確認）
