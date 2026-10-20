# Buddy Host

AI Buddy Tour v2 的家中主機服務。需要 [uv](https://docs.astral.sh/uv/)，Python 固定 3.12。

```bash
uv sync                      # 一般開發（FastAPI、測試）
uv sync --group speech       # 要實際合成語音時（torch、KittenTTS 2、Whisper，約數 GB）
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python -m buddy_host  # 啟動服務（旅程端點會回 503，沒有指定準備器）
uv run python -m buddy_host --replay-dir DIR     # 重播既有介紹，不呼叫 Claude
uv run python -m buddy_host --max-llm-calls N    # 真實準備；Claude 呼叫硬上限 N 次
```

主機上的設定與機密一律放在 `~/.buddy-host/`（可用 `BUDDY_HOST_HOME` 改位置），**不入 repo**：

| 檔案／目錄 | 內容 |
|---|---|
| `config.toml` | `listen_host`（Tailscale 位址，不接受 `0.0.0.0`）、`listen_port`、`token` |
| `claude-token` | `claude setup-token` 產生的 OAuth token（只用 Claude Pro 訂閱，不用 API key） |
| `voice/F2/` | 參考聲音 `ref_24k.wav` 與逐字稿 `ref_text.txt`（缺逐字稿會直接報錯） |
| `usage.jsonl` | 每次 Claude 呼叫的用量紀錄 |
| `journey.json` | 旅程記憶：這趟去過哪裡、永久記錄講過的景點與稿子（是位置歷史，不入 repo；壞檔會改名留存） |
| `out/`、`cache/` | 合成產物、驗收紀錄、Overpass／Wikipedia 快取 |
| `out/reports/` | 每趟一份用量報告 `tour-<開始時間>.json`（見下方「額度與用量報告」） |

## 語音管線（`buddy_host.speech`）

稿子 → 前處理（數字轉中文、去假名、切句、併成約 90 字一段）→ KittenTTS 2 合成 →
Whisper 轉寫比對 CER（阿拉伯／中文數字先統一）→ 不合格換 seed（最多 4 次）→ 拆句 →
拆分句 → 跳過。每段每次嘗試的 seed 與 CER 都寫進 `*.log.json`。

```bash
uv run python -m buddy_host.speech --text-file 稿子.txt --name demo
```

### 實測（M3／16 GB，2026-10-19）

名花之里原稿（含阿拉伯數字與日文假名，`docs/spikes/2026-10-18-kittentts2/texts/35_nabana_original.txt`）：

| 項目 | 數值 |
|---|---|
| 輸出 | 159.3 秒、24 kHz 單聲道 wav；10 段全數通過、0 段跳過 |
| 總耗時 | 707 秒（含模型載入 21 秒另計）；RTF 4.44 |
| 嘗試次數 | 16 次，5 段需要重試；錄取版本 CER 最大 0.122 |
| 合成／驗收 | 合成 626 秒、Whisper 驗收 81 秒 |
| 語速 | 約 4.6 字／秒（30～45 秒 ≈ 137～206 字） |

踩到的坑：逐句合成時，只有兩個字的「哇！」四個 seed 全部驗收失敗（Whisper 對超短音訊會亂寫），
所以前處理會把相鄰句子併成每段約 90 字再合成；整段失敗才依序往下拆。

## 旅程 API（`buddy_host.tour`）

都需要 `X-Buddy-Token`（有設 token 時）。準備很慢，所以位置回報立刻回應，準備在背景進行：
同一時間只跑一次，期間只保留最新位置；移動超過 250 公尺或旅人狀態改變才為前方重新準備。

| 端點 | 用途 |
|---|---|
| `POST /v1/tour/start` | 出發。帶 `lat`、`lon`、`heading_deg`、`mode`（walking／driving）、`companions`（solo／couple／family／friends）、`with_children`、`local_time`（帶時區的 ISO）；立刻準備起點周邊；回應 `resumed`：距離上次活動不到 2 小時且上一趟沒按結束，就接續同一趟 |
| `POST /v1/tour/location` | 位置與旅人狀態回報（同上欄位）；還沒出發回 409 |
| `POST /v1/tour/played` | App 回報一段介紹**播完**了（`{"id": …}`），主機才記成「講過」；不認得的 id 直接忽略（回 200） |
| `POST /v1/tour/end` | 結束；回傳 `summary`（本趟用量摘要，沒有進行中的旅程時是 `null`），並寫出用量報告 |
| `GET /v1/tour/narrations?after=N` | 輪詢：`active`、`preparing`、`stopped_reason`（`quota`／`llm_budget`／`forbidden_model`）、序號大於 N 的介紹（含景點座標與秒數） |
| `GET /v1/tour/audio?id=…` | 下載一段介紹的 wav |

**Claude 用量保護**：`--max-llm-calls N` 用 `BudgetedLlm` 包住 Claude 呼叫，次數用完就停止準備並回報 `llm_budget`。
一次準備最多 `limit(2) × (1 + 重寫次數)` 次呼叫；整趟次數 ≈ 起點那次 ＋ 路線長度 ÷ 250 公尺 × 2。

**額度與用量報告**（設計文件第 11 節）：
- Claude 回報額度用完（`rate_limit_event` 的 `status=rejected`，或錯誤文字 `hit your … limit`）時，`stopped_reason` 變成 `quota`，主機停止準備；不設每趟用量上限。
- 恢復：App 每次回報位置時檢查，過了 `resetsAt`（epoch 秒）就以最新位置重新準備，這次準備本身就是探測，仍被拒絕就依新的 `resetsAt` 再等。事件沒帶 `resetsAt` 時隔 15 分鐘再試。`llm_budget`、`forbidden_model` 不會自動恢復。額度恢復時 App 的提示自動消失，不念語音。
- 用量報告從 `usage.jsonl` 篩出本趟（開始到結束）的呼叫：每次呼叫的用途、模型、時間、token、`unifiedWindows`（5 小時／7 天）用量與是否撞到上限；`totals.utilization` 的「變化」是第一次與最後一次呼叫之後的差（不含第一次呼叫本身的消耗）。

**旅程記憶**（`buddy_host.tour.journey`，設計文件第 7 節）：
- 「講過」以 App 回報播完為準；主機準備好但 App 丟掉的不算。App 送不出去的回報會留著，下次輪詢連上時補送。
- 一趟從出發到按結束；沒按結束（App 被關掉）而隔不到 2 小時再出發就接續同一趟，接續時用量報告涵蓋整趟；超過 2 小時的舊趟會先替它寫完用量報告再開新的一趟。
- 每次寫稿都帶：這趟最近 5 個講過的地方名（`recent_topics`），以及這個地方以前最近 2 次講過的稿子、各截 300 字（`told_before`）。經過以前講過的地方，個性檔要求換個角度講。
- **快取**：稿子的指紋包含 `recent_topics`（稿子可能寫「剛剛的 A」），所以同一條路線重跑不再保證命中舊稿；起點那一段（還沒講過任何地方）仍可命中。
- `--replay-dir` 模式不寫 `journey.json`（桌上測試不該污染真實的永久記錄）。
