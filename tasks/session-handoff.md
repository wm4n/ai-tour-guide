# Session Handoff — AI Tour Guide

> 這份文件給下一個 Claude session 用，目的是讓對方在 zero context 下能直接接手繼續推進。

**前次 session 結束時間**：2026-05-09
**前次 session 主要產出**：v1 設計文件、Plan A 實作計畫、OpenSpec change skeleton + artifacts、後端 venv + deps 就位

---

## 1. 專案總覽

可帶出門的 AI tour guide 行動 App。使用者按「開始旅程」+ 選 persona（角色）後，App 在前景與背景持續偵測位置；走進景點 100m 範圍時，AI 自動以該 persona 的口吻、音色、語速串流播報旁白；可隨時 push-to-talk 提問。

技術棧：
- **Backend**：Python 3.12 / FastAPI / LiteLLM / google-genai / pytest（在 `backend/` 目錄）
- **App**：Flutter（尚未開始）
- **AI 服務 v1**：全 Gemini free tier（LLM / TTS / STT）
- **POI 來源**：OSM Overpass + Wikipedia（食家 persona 用 Google Places）
- **部署 v1**：Cloud Run（Plan F 才開始部署）

完整設計：`docs/superpowers/specs/2026-05-08-ai-tour-guide-design.md`

---

## 2. 漸進式 6 個 Plan 路線

| Plan | 名稱 | 狀態 | 文件 |
|---|---|---|---|
| **A** | Backend MVP — 單 persona narration | **執行中**（見下節進度）| `docs/superpowers/plans/2026-05-08-plan-a-backend-mvp.md` |
| **B** | Flutter App MVP — 消費 Plan A 後端 | 未開始 | 待寫 |
| **C** | Persona 系統擴充 + 雙語（4 persona、zh-TW + en、persona-coloured 訊息）| 未開始 | 待寫 |
| **D** | Push-to-talk Q&A | 未開始 | 待寫 |
| **E** | 食家 persona + Google Places | 未開始 | 待寫 |
| **F** | 背景定位 + 部署上線 | 未開始 | 待寫 |

---

## 3. 目前進度（Plan A 進行中）

### Git 已 commit 的 3 個 commits

```text
1d35e7c chore(openspec): add backend-narration change (proposal/design/specs/tasks)
9240383 docs: add Plan A — backend MVP implementation plan
c9a6ba0 docs: add AI tour guide v1 design spec
```

### OpenSpec 流程（已採用 opsx workflow）

OpenSpec change：`backend-narration`（在 `openspec/changes/backend-narration/`）

| Phase | Skill | 狀態 |
|---|---|---|
| 1 | `opsx:new` + 填 proposal | ✅ 完成（commit `1d35e7c`） |
| 2 | `opsx:ff`（產生 design + specs + tasks） | ✅ 完成（同上 commit） |
| 3 | `opsx:apply`（實作 Plan A 29 tasks） | 🟡 部分完成（見下方）|

### Plan A Task 1（已實質完成、未 commit）

工作目錄：`/Users/william.chao/workspace/flutter/ai-tour-guide`

已存在但**尚未 commit** 的檔案（git status 顯示為 `?? backend/`）：
- `backend/pyproject.toml`
- `backend/ruff.toml`
- `backend/pytest.ini`
- `backend/.env.example`
- `backend/README.md`
- `backend/src/tour_guide/__init__.py`
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`
- `backend/tests/{unit,integration,smoke}/__init__.py`
- `backend/.venv/`（已建立、所有 deps 已 `pip install -e ".[dev]"`，含 fastapi, litellm, google-genai, pytest 9.0.3, ruff 等）

**驗證 venv 已就位**：
```bash
cd backend && .venv/bin/pytest --version   # → pytest 9.0.3
```

### Plan A Task 2-29（尚未開始）

請參閱 `docs/superpowers/plans/2026-05-08-plan-a-backend-mvp.md` 的 Task 2 起到 Task 29，每個 task 內含：
- 完整測試碼（red → green → refactor 模板）
- 完整實作碼
- 該 task 的 commit 訊息範本

---

## 4. 下一步具體 action（依優先序）

### Step 1：先 commit Plan A Task 1（解開「未 commit」狀態）

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide
git add backend/pyproject.toml backend/ruff.toml backend/pytest.ini backend/.env.example backend/README.md backend/src/ backend/tests/
git commit -m "feat(backend): initialize Python project skeleton

- pyproject.toml with FastAPI, LiteLLM, google-genai, pytest, ruff
- ruff + pytest config with real_provider marker
- src/ layout, empty packages
- README and .env.example"
```

注意：**不要** `git add backend/.venv/`。`.gitignore` 已涵蓋 venv 路徑。

### Step 2：往下做 Plan A Task 2 到 Task 29

直接照 `docs/superpowers/plans/2026-05-08-plan-a-backend-mvp.md` 走，每個 task 的 step 都已寫齊。

**執行慣例**：
- TDD red → green → refactor → commit，每 task 一個 atomic commit
- 跑測試用：`cd backend && .venv/bin/pytest tests/<path> -v`
- 跑 ruff 用：`cd backend && .venv/bin/ruff check src/ tests/`
- 啟動 dev server 用：`cd backend && GEMINI_API_KEY=anything-fake-for-import .venv/bin/uvicorn tour_guide.main:app --reload`

### Step 3：Plan A 完成後驗證

依 Plan A § "Plan A — Done Definition"：
1. `cd backend && .venv/bin/pytest -v` → ~40+ green，real_provider smoke 自動 skip
2. `cd backend && .venv/bin/ruff check src/ tests/` → 乾淨
3. `curl /health` → 200
4. `curl /poi/nearby?lat=25.1023&lon=121.5482&radius=500&lang=zh-TW` → 真實 OSM POI 列表
5. `curl -N -X POST /narration ...`（需要使用者設真實 `GEMINI_API_KEY`）→ 串流 Gemini 旁白音訊

### Step 4：Plan A 通過後

呼叫 `superpowers:writing-plans` skill 寫 **Plan B（Flutter App MVP）**，並 commit。

---

## 5. 必須知道的 context（避免重蹈覆轍）

### 5.1 Subagent 權限限制

之前嘗試用 3-phase subagent dispatch 跑 `/opsx:apply`，**subagent 的 sandbox 權限獨立於 project 的 `.claude/settings.local.json` allowlist**，即使主 session 能跑的指令，subagent 也會被擋。

**結論**：目前 Plan A 剩餘 task 走 inline 主 session 比較順。若你想試 subagent，先確認 user-level `~/.claude/settings.json` 有給足權限，再考慮。

### 5.2 Cwd 在多個 Bash call 之間不穩定

實測發現：`cd backend && cmd` 之後下一個 call 的 cwd 有時回到 root，有時保持 backend。**安全做法**：每個需要 backend cwd 的指令都自己帶 `cd backend && ...`。

### 5.3 Permission allowlist 樣式

User 偏好**緊縮** allowlist（具體指令 > 寬 wildcard）。`.claude/settings.local.json` 目前只允許：
- `Bash(python3.12 -m venv .venv)` — 完全特定
- `Bash(.venv/bin/pip install *)` — `pip install` 後可以任意參數
- 其他基本指令（git、grep、awk 等）

新指令要先試試，被擋了再請使用者加。

### 5.4 GEMINI_API_KEY 狀態

**未設**。Plan A 全部 29 個 task 設計上都用 fake provider 離線測試，不需要真實 key。唯一需要真實 key 的：
- `Task 28` 的 `@pytest.mark.real_provider` smoke test → 沒 key 會自動 skip
- `Task 26` 的手動 server smoke → 用 `GEMINI_API_KEY=anything-fake-for-import` 即可（plan 已寫）
- 將來真要 demo `/narration` 串流 → 需要真實 key

設真實 key：使用者去 https://aistudio.google.com/apikey 拿，然後 `export GEMINI_API_KEY=...` 或寫進 `backend/.env`。

### 5.5 OpenSpec 工具狀態

`opsx:*` plugin 已安裝。完整 skill 清單在系統 reminder 中。常用：
- `opsx:apply` — 實作 tasks
- `opsx:continue` — 接續下一個 artifact
- `opsx:status`（？）— 查當前進度
- `opsx:verify` — 驗證實作對齊 spec
- `opsx:archive` — 完成歸檔

### 5.6 Markdown lint 警告

之前的 spec / plan 文件有些 markdownlint 警告（CJK 字元 + 程式碼 fence 缺語言標籤），對 skill 功能無影響，可忽略。

---

## 6. 關鍵檔案索引

| 用途 | 路徑 |
|---|---|
| 整體 v1 設計（架構、決策、persona、API） | `docs/superpowers/specs/2026-05-08-ai-tour-guide-design.md` |
| Plan A 實作計畫（29 個 TDD tasks） | `docs/superpowers/plans/2026-05-08-plan-a-backend-mvp.md` |
| OpenSpec change 主目錄 | `openspec/changes/backend-narration/` |
| OpenSpec proposal | `openspec/changes/backend-narration/proposal.md` |
| OpenSpec design | `openspec/changes/backend-narration/design.md` |
| OpenSpec spec | `openspec/changes/backend-narration/specs/backend-narration/spec.md` |
| OpenSpec tasks（25 群組）| `openspec/changes/backend-narration/tasks.md` |
| Backend 程式碼（建構中） | `backend/src/tour_guide/` |
| Backend 測試 | `backend/tests/` |
| Backend venv | `backend/.venv/`（gitignored） |
| Project 工作流規範 | `CLAUDE.md` → 連結到 `AGENTS.md` |
| 此 handoff 文件 | `tasks/session-handoff.md` |

---

## 7. 跟使用者互動的偏好（從前次 session 觀察）

- 全程**繁體中文**對話（CLAUDE.md 全域規範）
- 偏好**簡潔回應 + 具體選項**（不要長篇 narrate）
- 推薦時**講清楚 trade-off + 推薦哪個 + 為什麼**，給使用者拍板
- 重要決策（commit、安裝、permission 變動）**先 propose 等確認**
- 尊重 user 的緊縮 permission style，不要主動加寬 allowlist

---

## 8. 給下一個 session 的開場 prompt 模板

```text
我想接續上次的 AI tour guide 專案進度。請先讀 tasks/session-handoff.md，
然後按其中「下一步具體 action」往下做。
從 Step 1（commit Plan A Task 1）開始，每個 Plan A task 完成 commit 一次。
```

—— END HANDOFF
