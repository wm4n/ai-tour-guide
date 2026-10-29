# Buddy Host

AI Buddy Tour v2 的家中主機服務。需要 [uv](https://docs.astral.sh/uv/)，Python 固定 3.12。

```bash
uv sync                      # 一般開發（FastAPI、測試）
uv sync --group speech       # 要實際合成語音時（torch、KittenTTS 2、Whisper，約數 GB）
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python -m buddy_host  # 啟動服務（旅程與問答端點會回 503，沒有指定準備器）
uv run python -m buddy_host --replay-dir DIR     # 重播既有介紹，不呼叫 Claude；問答回固定的假答案（提示音）
uv run python -m buddy_host --max-llm-calls N    # 真實準備與問答；兩者共用 Claude 呼叫硬上限 N 次
```

主機上的設定與機密一律放在 `~/.buddy-host/`（可用 `BUDDY_HOST_HOME` 改位置），**不入 repo**：

| 檔案／目錄 | 內容 |
|---|---|
| `config.toml` | `listen_host`（Tailscale 位址，不接受 `0.0.0.0`）、`listen_port`、`token`、`voice`（用哪個參考聲音，預設 `F2`） |
| `claude-token` | `claude setup-token` 產生的 OAuth token（只用 Claude Pro 訂閱，不用 API key） |
| `voice/<名稱>/` | 參考聲音 `ref_24k.wav` 與逐字稿 `ref_text.txt`（缺逐字稿會直接報錯）；選填的 `voice.toml` 是這個聲音的語速、停頓、App 上的名稱與描述（見下方「聲音設定」），**有 `voice.toml` 的才列在 App 上** |
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
uv run python -m buddy_host.speech --text-file 稿子.txt --name demo --voice M1 --answer  # 當成回答問題
```

### 聲音設定（`voice/<名稱>/voice.toml`，選填）

有些參考聲音合成出來偏慢（約 4.4 字／秒），聽起來像在慢慢唸稿。每個聲音可以自己調：

```toml
speed = 1.2                      # 語速倍率（0.5～2.0），主動介紹與回答問題都套用
answer_max_pause_seconds = 0.45  # 只有回答問題時，超過這個長度的停頓縮到這個長度
display_name = "示範女聲"              # App 上顯示的名稱（預設為資料夾名）
description = "女聲・溫暖"          # App 上的簡短描述
```

- **App 的聲音清單**：只列出有 `voice.toml` 的資料夾（篩選時留下的候選不列）。
  `GET /v1/voices` 回傳每個聲音的 `name`（資料夾名）、`display_name`、`description`、
  `key`（聲音鍵）、`phrases_ready`（目前語速的固定短句是否都已產生），以及目前使用中的 `current`；
  每次請求都重讀硬碟，改了名稱、描述、語速不必重啟。`voice.toml` 寫壞的聲音只略過那一個。
  `GET /v1/voices/{name}/phrases/{number}` 下載某聲音目前語速的某句短句（不存在回 404）。都需要 `X-Buddy-Token`。

- **語速**：在聲碼器之前把 mel 的時間軸線性插值壓短，再交給聲碼器重新生成聲音，音高與音色不變
  （上游 CosyVoice 的做法）。對成品音檔做時間伸縮（相位聲碼器）試過，聲音怪，不採用。
  Whisper 驗收檢查的是加速後的聲音。實作換掉了 kittenml 的 `S3Codec.decode`，
  `tests/speech/test_engines.py` 會在 kittenml 改版時提醒要重新檢查。
- **停頓**：只壓縮回答問題的停頓（像平常聊天）；主動介紹保留停頓與段落換氣（像在說故事），
  被問題打斷時找句子開頭的 `unit_starts` 也照舊。靜音的判斷與 `librosa.effects.split` 相同
  （以整段最大音量為準，低於 35 dB），說話的部分一個取樣都不動，開頭與結尾各留上限的一半。
- **沒有 `voice.toml` 的聲音一切照舊**：原速（完全走 kittenml 原本的解碼）、不壓停頓。
- **換聲音**：改 `config.toml` 的 `voice` 後重新啟動。介紹快取是「稿子與聲音無關、音檔依聲音分開」：
  `out/narrations/<景點>.meta.json` 每個景點一份（稿子與指紋），音檔與合成紀錄放
  `out/narrations/<聲音鍵>/`（聲音鍵＝`名稱@語速`，如 `F2@1.2`）。換聲音只重新合成、不會再呼叫 Claude；
  切回用過的聲音直接命中。聲音可設定之前留下的平放音檔不再使用，用到時從稿子重新合成。
- **固定短句**：App 內建的（`app/assets/phrases/`）不會跟著換。每個聲音的短句用
  `python -m buddy_host.speech.phrases --voice <聲音> --auto` 自動產生（每句試多個 seed，
  挑通過驗收、CER 最低且較短的一版），放在 `out/voice-phrases/<聲音鍵>/<編號>.wav`；
  改了語速，聲音鍵就變、要重新產生。某句沒有版本通過時不寫入、列出該句並以非 0 結束
  （`--max-seeds` 可加大）。人工挑選的舊流程（不帶 `--auto`、`--finalize`）維持原樣。

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
| `GET /v1/tour/narrations?after=N` | 輪詢：`active`、`preparing`、`stopped_reason`（`quota`／`llm_budget`／`forbidden_model`）、序號大於 N 的介紹（含景點座標、秒數，以及 `unit_starts`：各個合成單位〔句〕開始播放的秒數，被問題打斷時 App 回到那一句的開頭；從 wav 裡單位之間的靜音偵測，快取命中的舊介紹也有，讀不出來時是空陣列） |
| `GET /v1/tour/audio?id=…` | 下載一段介紹的 wav |

**Claude 用量保護**：`--max-llm-calls N` 用 `BudgetedLlm` 包住 Claude 呼叫，次數用完就停止準備並回報 `llm_budget`。
一次準備最多 `limit(2) × (1 + 重寫次數)` 次呼叫；整趟次數 ≈ 起點那次 ＋ 路線長度 ÷ 250 公尺 × 2。

**額度與用量報告**（設計文件第 11 節）：
- Claude 回報額度用完（`rate_limit_event` 的 `status=rejected`，或錯誤文字 `hit your … limit`）時，`stopped_reason` 變成 `quota`，主機停止準備；不設每趟用量上限。
- 恢復：App 每次回報位置時檢查，過了 `resetsAt`（epoch 秒）就以最新位置重新準備，這次準備本身就是探測，仍被拒絕就依新的 `resetsAt` 再等。事件沒帶 `resetsAt` 時隔 15 分鐘再試。`llm_budget`、`forbidden_model` 不會自動恢復。額度恢復時 App 的提示自動消失，不念語音。
- **旅程準備與問答共用同一個額度閘門**（`llm.quota.QuotaGate`）：任一邊撞到上限，兩邊一起停（問答直接回 `failed／quota`，不再呼叫 Claude）；恢復後下一次要呼叫 Claude 的就是探測。
- 用量報告從 `usage.jsonl` 篩出本趟（開始到結束）的呼叫：每次呼叫的用途、模型、時間、token、`unifiedWindows`（5 小時／7 天）用量與是否撞到上限；`totals.utilization` 的「變化」是第一次與最後一次呼叫之後的差（不含第一次呼叫本身的消耗）。

## 問答 API（`buddy_host.qa`）

都需要 `X-Buddy-Token`。問答在 `--max-llm-calls` 模式是真的（Claude＋語音管線）；`--replay-dir` 模式回**固定的假答案**（`qa.replay`：固定文字、每段一個提示音，問題裡有「上網」兩字時假裝動用上網工具），只用來在桌上或模擬器跑通 App 流程，不消耗額度。兩者都不給時回 503。語音辨識由 App 做，主機收文字，回的是**語音**（逐段下載）。

| 端點 | 用途 |
|---|---|
| `POST /v1/qa/ask` | 發問。帶 `question`（1～500 字）、位置與旅人狀態（欄位同 `/v1/tour/start`），`more: true` 表示「再多說一點」；回 `{"id": …}` |
| `POST /v1/qa/ask-photo` | 拍照提問。欄位同 `/v1/qa/ask`，另加 `image_base64`（JPEG／PNG）；`question` 沒給就是「這是什麼？」；`heading_deg` 是拍照時手機的**指南針**方向（不是走路的方向）。回 `{"id": …}`，之後和一般問答一樣輪詢。不是 JPEG／PNG 或不是有效 base64 回 400、超過 8 MB 回 413、主機沒開放拍照回 503 |
| `GET /v1/qa/answer?id=…` | 輪詢：`status`（`answering`＝還在寫或還在合成、`done`＝文字寫完且每段都做完、`failed`）、`segments`（已經可以下載的段落 `[{index, audio_seconds}]`，依序、編號連續）、`first_segment_seconds`（收到問題 → 第一段可下載）、`text`（Claude 的完整答案，寫完才有）、`searching_web`（Claude 動用了上網工具，App 可以說「我上網查一下」）、`reason`（`failed` 時：`quota`／`llm_budget`／`forbidden_model`／`no_audio`／`cancelled`＝App 放棄／`error`）；不認得的 id 回 404 |
| `POST /v1/qa/cancel?id=…` | App 不要這個答案了（旅程結束、逾時）：停掉 Claude 的呼叫（行程一併殺掉）與還沒做的合成、還掉 GPU 號碼牌；回 `{"cancelled": true／false}`（已結束的答案是 false），不認得的 id 回 404 |
| `GET /v1/qa/audio?id=…&index=N` | 下載答案的第 N 段 wav；還沒做好或不存在回 404 |

- 每個問題都是一次**全新**的 Claude 呼叫（Sonnet，不接受覆寫；Fable 會被擋下），用量照常寫進 `usage.jsonl`（`purpose=qa`）。
- 送給 Claude 的 prompt：問題、位置與行進方向、旅人狀態、附近最多 5 個景點（維基摘要各截 200 字）、這趟剛講過的地方、這些景點以前講過的稿子（沿用旅程記憶的長度上限）。附近景點查不到（或超過 10 秒）就空手回答。
- `more: true` 時再帶「剛剛講的那段」：**只算 App 回報播完的**（`/v1/tour/played`），準備好但還沒播的不算。
- 回答過程中 Claude 使用 `WebSearch`／`WebFetch` 時，`searching_web` 變成 `true`；查資料之前說的開場白不念（指示 Claude 不要先說，程式也會丟掉還沒吐出的文字）。
- **答案不等寫完**：串流的文字每寫完一句（。！？或換行）就切段，第一段是第一句（太短的先併入下一句；第一句超過 40 字就不等句號，在第一個夠長的逗號先切），之後併到約 60 字一段；一段交給 `SpeechPipeline`（Whisper 驗收、換 seed、拆句、仍不行就跳過，規則同主動介紹），做好就出現在 `segments`。被跳過的段落不佔編號；全部都被跳過回 `failed／no_audio`。
- Claude 中途失敗時，已經做好的段落還在（`failed` 但 `segments` 有東西），由 App 決定要不要播；還沒做的不做。
- 音檔放在 `~/.buddy-host/out/answers/<id>/`，只留最近 50 個答案，被淘汰的連音檔一起刪。
- **GPU 排程**（`speech.scheduler.SpeechScheduler`，設計文件第 9.1 節）：家中 Mac 只有一顆 GPU，介紹與問答共用同一個語音管線，**問答優先**。合成單位＝管線裡的一個 chunk（含換 seed 重試）：
  - 問答一進來，主動介紹在**下一個單位開始前**暫停；正在合成的單位做完才讓路，不會被打斷；問答全部做完介紹才繼續，所以介紹最終一定會完成。
  - **整個答案持有優先權**：從開始回答（呼叫 Claude 之前）到答案結束，包含等 Claude 寫下一段的空檔，介紹都不會趁機開始新單位（否則下一段問答又要等一個介紹單位）；代價是 Claude 寫字或上網查的時候 GPU 閒著，介紹也暫停。
  - 多個問答依先後順序一個答案一個答案做，不會同時合成。
  - 代價：介紹合成到一半時進來的問題，要等那一個單位（約數十秒，M3）做完才開始。
- 「收到問題 → 第一段可下載」每答一題記一筆到 `~/.buddy-host/qa-latency.jsonl`，用量報告的 `qa` 區塊有本趟的次數、平均與最大值。

**旅程記憶**（`buddy_host.tour.journey`，設計文件第 7 節）：
- 「講過」以 App 回報播完為準；主機準備好但 App 丟掉的不算。App 送不出去的回報會留著，下次輪詢連上時補送。
- 一趟從出發到按結束；沒按結束（App 被關掉）而隔不到 2 小時再出發就接續同一趟，接續時用量報告涵蓋整趟；超過 2 小時的舊趟會先替它寫完用量報告再開新的一趟。
- 每次寫稿都帶：這趟最近 5 個講過的地方名（`recent_topics`），以及這個地方以前最近 2 次講過的稿子、各截 300 字（`told_before`）。經過以前講過的地方，個性檔要求換個角度講。
- **快取**：稿子的指紋包含 `recent_topics`（稿子可能寫「剛剛的 A」），所以同一條路線重跑不再保證命中舊稿；起點那一段（還沒講過任何地方）仍可命中。
- `--replay-dir` 模式不寫 `journey.json`（桌上測試不該污染真實的永久記錄）。

**拍照提問**（`qa/photos.py`，設計文件第 8 節第 7 點）：
- 照片只存在主機本機 `~/.buddy-host/photos/`（在 repo 外，資料夾 0700），檔名是隨機字串、權限 0600；**保留 24 小時**：每次發問、每次存新照片、主機啟動時，以及每小時的背景清理都會清掉過期的。只收 JPEG／PNG，上限 8 MB（請求欄位上限對齊，不白白解碼更大的東西）。寫到一半失敗不留殘缺的照片。
- Claude 用 `Read` 工具看照片（`--add-dir` 開放照片資料夾；做法見 `docs/spikes/2026-10-19-claude-headless`）。prompt 說明手機對著哪個方位（指南針），附近景點的「前後左右」以那個方向為準；沒有指南針讀數就明說方向不明。
- **照片內容是第三方內容**（招牌、海報、QR 旁邊的字）：可能夾帶「去讀某個檔案、再把它送出去」之類的指示。防護：
  - **拍照的問題不給上網的工具**（沒有 `WebSearch`／`WebFetch`，prompt 也明說這一題不能上網、照片裡的字不是指示），Claude 讀到什麼都送不出主機；
  - `Read` 只准讀照片資料夾：權限規則 `Read(//…/photos/**)`（絕對路徑要兩個斜線開頭），同層的 `claude-token` 讀不到（無人值守時沒被允許的讀取會被拒絕）；
  - **每次呼叫都用 `--tools` 把內建工具縮到這次需要的**（沒有需要就全關；這個旗標**對所有呼叫生效**——旅程寫稿、一般問答、拍照都是）：預設的工具集連 Bash 都有、而且唯讀指令（如 `cat`）免詢問，網頁內容也可能夾帶指示。**旗標還沒有用真實 Claude 驗證過**（`claude --help` 看得到、`--tools ""` 的行為依官方文件），第一次跑真實模式請先用最小請求各試一次（寫稿、一般問答、拍照）。
  - 殘留風險：`--add-dir` 開的是整個照片資料夾，Claude 讀得到 24 小時內的其他照片；這些防護**都還沒有在真實 Claude 上驗證過**（見下）。
- 照片會被主機交給 Claude，**影像會送到 Anthropic**（和問答的文字一樣走使用者的 Claude Pro 訂閱）。
- **真實 Claude 讀圖與 `--tools`／限定路徑的 `Read` 規則尚未驗證**：目前全部是 fake LLM；要驗證須使用者先同意呼叫次數（每次約 50k～80k 輸入 token）。規則語法來自官方文件，但「讀得到照片、讀不到別處」要實際打一次才算數；`--tools` 是新加的旗標，`claude --help` 看得到、尚未真實呼叫過。

