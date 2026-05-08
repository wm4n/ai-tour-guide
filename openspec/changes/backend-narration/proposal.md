## Why

v1 AI Tour Guide 需要一個可被 Flutter App 呼叫的後端，負責「給座標出旁白」的核心體驗：streaming LLM 生成 → 句子切分 → TTS 合成 → SSE 推送。Plan A 的目標是在進入 Flutter App 開發（Plan B）之前，先獨立驗證這條 pipeline 的可行性，並交付一個具備 Provider 抽象、完整 TDD 測試、可本機執行的 FastAPI 後端服務。

## What Changes

- **新增** `backend/` Python/FastAPI 專案（src layout，PEP 621 pyproject.toml）
- **新增** 3 個 HTTP endpoint：
  - `GET /poi/nearby` — 給座標回附近 POI 列表（OSM Overpass + Wikipedia）
  - `POST /narration` (SSE) — 給 POI + persona 串流回 `meta/text/audio/end/error` events
  - `GET /health` — 服務健康檢查
- **新增** 5 個核心服務模組：`POIService`、`NarrationService`、`SentenceSplitter`（純函式）、`PromptBuilder`（純函式）、`ConfidenceClassifier`（純函式）
- **新增** Provider 抽象介面（`LlmProvider` / `TtsProvider`）+ LiteLLM / Gemini 實作 + Fake 測試替身
- **新增** 外部 client 封裝：`OverpassClient`、`WikipediaClient`
- **新增** 兩層快取：`POICache`（TTL 30 天）、`NarrationCache`（key：poi+persona+lang+length）
- **新增** persona 資源檔系統：YAML 定義 `history_uncle`（Plan A 僅 zh-TW 單一 persona）
- **新增** 29 個 TDD 任務（unit / integration / smoke test 三層）

**Plan A 範圍外（defer）**：`/qa` endpoint（Plan D）、其餘 4 個 persona（Plan C）、食家 persona + Google Places（Plan E）、Cloud Run 部署 + API Key 保護（Plan F）。

## Capabilities

### New Capabilities

- `backend-narration`: 後端旁白 pipeline 全功能 — POI 查詢、LLM streaming、句子切分、TTS 合成、SSE 推送、兩層快取、Provider 抽象、TDD 測試套件

### Modified Capabilities

（無 — 這是全新後端專案，不涉及現有 spec 的需求異動）

## Impact

**API 表面**（新增，無 breaking change）：
- `GET /poi/nearby?lat=&lon=&radius=&lang=&persona=` → `{ pois: [...] }`
- `POST /narration` body `{ poi_id, persona, lang, length, force_regenerate }` → SSE stream
- `GET /health` → `{ status, uptime_s }`
- 所有 response 格式詳見 `docs/superpowers/specs/2026-05-08-ai-tour-guide-design.md` 第 6 節

**新增外部依賴**：
- `litellm` — LLM 抽象（Gemini via LiteLLM proxy）
- `google-genai` — Gemini TTS SDK
- `httpx` — async HTTP client（Overpass、Wikipedia）
- `sse-starlette` — FastAPI SSE 支援
- `pydantic-settings` — 設定管理（環境變數）
- `pytest`, `pytest-asyncio`, `respx`, `freezegun` — 測試工具

**部署架構（v1）**：
- 本機 dev：`uvicorn tour_guide.main:app --reload`（搭配 fake providers 完全離線）
- 真機測試：手動部署到 Cloud Run staging（Plan F 才自動化）
- 快取路徑：容器 `/tmp/`（重啟會清，v1 可接受；v2 升 GCS bucket）

**不影響**：Flutter App（尚未存在）、任何現有模組
