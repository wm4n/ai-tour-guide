# Claude Code headless 實測（2026-10-19）

回答設計文件第 15 節第 1 項「Claude Code headless 在主機上的行為」。對應 issue #3。

## 方法

- 主機：Mac（M3／16 GB），Claude Code 2.1.302，`CLAUDE_CODE_OAUTH_TOKEN`（`claude setup-token`）
- 呼叫方式：`host/` 的 `ClaudeCliClient`（`claude -p --output-format stream-json --verbose --include-partial-messages --no-session-persistence --setting-sources project --disable-slash-commands --strict-mcp-config`），prompt 走 stdin，在空的工作目錄執行；所有 `ANTHROPIC_*` 環境變數已剝除
- 共 4 次 Haiku 呼叫（`claude-haiku-5-5`）：冷啟動 2 次、讀圖 1 次、本機 MCP 工具 1 次
- 重現：`cd host && uv run python -m buddy_host.probe.run_probe --confirm-calls 4`（會消耗 Claude Pro 額度）

## 結果

| 項目 | 結果 |
|---|---|
| OAuth token + `claude -p` | 可用；不需要 `--bare`、不需要 API key |
| 冷啟動延遲（每次都是新行程、新對話） | 總耗時 **3.1～3.3 秒**，第一個字 **2.1～2.5 秒**（CLI 回報的 `duration_ms` 1.4～1.7 秒，其餘是行程啟動） |
| 讀主機上的圖片檔 | 可以：給 `Read` 工具與 `--add-dir`，讀一張純紅 PNG，回答「紅色」；3.5 秒 |
| 呼叫本機 MCP 工具 | 可以：以 `--mcp-config` + `--strict-mcp-config` 掛上 stdio MCP 伺服器，Claude 呼叫 `mcp__probe__probe_nonce` 並原樣回傳暗號；4.0 秒 |
| stream-json 解析 | 4 次呼叫全部解析成功，沒有無法解析的行；`--include-partial-messages` 有逐字串流 |
| 隔離旗標 | `--setting-sources project`、`--disable-slash-commands`、`--strict-mcp-config`、`--no-session-persistence` 都被接受 |
| 超額付費 | `overageStatus: rejected`、`overageDisabledReason: org_level_disabled`，與「usage credits 已關閉」一致 |

## 發現（會影響後續票）

1. **`utilization` 不在 `rate_limit_event` 的頂層**，而是在 `unifiedWindows.five_hour` 與 `unifiedWindows.seven_day` 底下（各有 `utilization` 與 `resetsAt`）；頂層有 `status`、`resetsAt`、`rateLimitType`、`overageStatus`。設計文件第 11 節原本假設的欄位位置要修正。`usage.jsonl` 存的是整個事件，資料沒有遺失，但 #13 讀額度時要讀對地方。
2. **即使是「只回覆 OK」，每次呼叫也帶約 25k 個輸入 token**（大部分是 cache 讀取，約 17k 讀取 + 8k 建立）；用到 `Read` 或 MCP 工具時升到 51k～77k。這是 Claude Code 的系統提示與工具定義，每次新對話都要付。要降低額度消耗，之後可以評估用 `--tools` 縮小工具集。
3. 4 次 Haiku 呼叫後額度顯示沒有變動（5 小時視窗 0.06、7 天視窗 0.33，精度只到 0.01），所以這 4 次 Haiku 的額度成本小於可量測的粒度。**Sonnet 寫稿的額度成本尚未量測**（#6）。
4. 7 天視窗在測試開始時已經用了 33%：這個訂閱同時給日常的 Claude Code 使用，旅程當天的額度要預留。

## 沒有驗證的

- Sonnet／Opus 的延遲與額度成本（只測了 Haiku）
- 會上網的呼叫（`WebSearch`／`WebFetch`）
- 長時間連續呼叫會不會觸發 `rate_limit_event` 的 `rejected`
- Fable 拒絕只在單元測試驗證（請求端與 `modelUsage` 事後檢查），沒有真的去要求 Fable
