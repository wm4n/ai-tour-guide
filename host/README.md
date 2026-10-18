# Buddy Host

AI Buddy Tour v2 的家中主機服務。需要 [uv](https://docs.astral.sh/uv/)，Python 固定 3.12。

```bash
uv sync                      # 一般開發（FastAPI、測試）
uv sync --group speech       # 要實際合成語音時（torch、KittenTTS 2、Whisper，約數 GB）
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python -m buddy_host  # 啟動服務
```

主機上的設定與機密一律放在 `~/.buddy-host/`（可用 `BUDDY_HOST_HOME` 改位置），**不入 repo**：

| 檔案／目錄 | 內容 |
|---|---|
| `config.toml` | `listen_host`（Tailscale 位址，不接受 `0.0.0.0`）、`listen_port`、`token` |
| `claude-token` | `claude setup-token` 產生的 OAuth token（只用 Claude Pro 訂閱，不用 API key） |
| `voice/F2/` | 參考聲音 `ref_24k.wav` 與逐字稿 `ref_text.txt`（缺逐字稿會直接報錯） |
| `usage.jsonl` | 每次 Claude 呼叫的用量紀錄 |
| `out/`、`cache/` | 合成產物、驗收紀錄、Overpass／Wikipedia 快取 |

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
