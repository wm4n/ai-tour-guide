# 家裡 Mac（主機）準備清單

家裡的 Mac 是正式使用時的主機：它跑 Claude Code、語音管線、景點準備，手機透過 Tailscale 連它。
這份清單做完，手機上的 App 就能連到它，接著照 `docs/device-verification.md` 驗收。

> 這個 repo 是公開的：下面的 token、參考聲音、Tailscale 位址**都不要寫進 repo**，只放在 `~/.buddy-host/`。
> 公司電腦不能裝 Tailscale，所以主機只放在家裡這台；開發用的筆電只負責編譯、把 App 裝到手機。

## 1. 工具

- [ ] Xcode Command Line Tools：`xcode-select --install`
- [ ] Homebrew，然後：
  ```bash
  brew install uv git
  brew install --cask tailscale-app     # 完整的 Mac App（選單列、登入畫面）；formula 的 `tailscale` 只有命令列
  ```
  `tailscale-app` 會跑系統安裝程式、要輸入 sudo 密碼：在自己的終端機執行，agent 沒辦法代裝。
- [ ] Claude Code CLI（主機以 `claude -p` 呼叫它）：依官方文件安裝，確認 `claude --version` 有輸出。
- [ ] 確認 Python 3.12 可用：`uv python install 3.12`（`uv sync` 會自己處理，但先裝可以早點發現網路問題）。

## 2. Tailscale

- [ ] 開啟 Tailscale App，用和 iPhone **同一個帳號**登入。
- [ ] 取得這台 Mac 的位址（`100.x.y.z`）：
  ```bash
  /Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4
  ```
- [ ] iPhone 從 App Store 裝 Tailscale、登入同一個帳號、開啟。
- [ ] 手機的 Tailscale 裡看得到這台 Mac 是「已連線」。

## 3. 程式碼與相依套件

```bash
git clone git@github.com:wm4n/ai-tour-guide.git   # 這台沒設 SSH key 就用 https://github.com/wm4n/ai-tour-guide.git
cd ai-tour-guide/host
uv sync --group speech      # 含 torch、KittenTTS 2、Whisper，約數 GB，要一段時間
uv run pytest -q            # 全綠才往下（不需要 GPU 或網路以外的東西）
```

- [ ] `uv sync --group speech` 成功。
- [ ] `uv run pytest -q` 全過。
- [ ] 第一次真正合成時會下載 KittenTTS（約 2 GB，存在 `~/.cache/huggingface/`）與 Whisper（約 460 MB，存在
      `~/.buddy-host/cache/`）的模型，這台 Mac 需要能連外網；M6 上約 2 分鐘。第 7 節的第一個聲音會順便下載。

## 4. 機密與設定（`~/.buddy-host/`，不入 repo）

```bash
mkdir -p ~/.buddy-host/voice
chmod 700 ~/.buddy-host
```

- [ ] **Claude token**：在這台 Mac 上執行 `claude setup-token`（需要 Claude Pro 訂閱），把印出的 token 存成
      `~/.buddy-host/claude-token`，權限 `chmod 600`。建議在這台重新產生，不要從別台複製。
- [ ] **參考聲音**：每個聲音一個資料夾 `~/.buddy-host/voice/<名稱>/`（名稱和原本那台完全一樣，短句目錄以它命名），
      各放三個檔：`ref_24k.wav`、`ref_text.txt`（逐字稿，缺了會直接報錯）、`voice.toml`（語速等；有它的聲音才會出現在
      App 清單、第 7 節才要跑）。在原本那台用 `ls ~/.buddy-host/voice/*/voice.toml` 列出要搬哪些；資料夾裡其他檔不用搬。
      這些檔不入 repo，用隨身碟或 AirDrop 從原本的機器搬；搬完刪掉中間的副本，再 `chmod -R go-rwx ~/.buddy-host/voice`。
      Finder 拖放會留下 `.DS_Store`，目前不影響。
- [ ] **App 連線 token**：產生一組隨機字串並記下來，等一下要填進 App：
  ```bash
  openssl rand -hex 16
  ```
- [ ] **`~/.buddy-host/config.toml`**：
  ```toml
  listen_host = "100.x.y.z"     # 第 2 節取得的 Tailscale 位址；不接受 0.0.0.0
  listen_port = 8765
  token = "上面產生的那組"
  ```
  設定檔不接受 `0.0.0.0` 或一般區網位址，這是刻意的：主機只讓 tailnet 內的裝置連。

## 5. 防止 Mac 睡著

主機睡著，手機就連不上。出門驗收期間：

- [ ] 接著電源，系統設定 →（電池／能源）→ 關閉「螢幕關閉時自動進入睡眠」，或在啟動主機的終端機用
      `caffeinate -is uv run python -m buddy_host --max-llm-calls 6`（`-i` 不閒置睡眠、`-s` 接電源時不睡眠）。
- [ ] 家裡 Wi-Fi 路由器不要在你不在時斷線；Mac 的 Tailscale 設為開機自動啟動。

## 6. 啟動前的驗證（先不呼叫 Claude）

```bash
cd ai-tour-guide/host
uv run python -m buddy_host --replay-dir ~/.buddy-host/out/narrations   # 重播模式：不耗額度
```

另開一個終端機：

```bash
curl -s http://100.x.y.z:8765/health
curl -s -H "X-Buddy-Token: <token>" http://100.x.y.z:8765/v1/status
```

- [ ] `/health` 有回應。
- [ ] 有 token 時 `/v1/status` 回得出來；不帶 token 回 401。
- [ ] 用 iPhone Safari 開 `http://100.x.y.z:8765/health`（手機的 Tailscale 開著）：能看到回應，代表手機連得到這台 Mac。

## 7. 為每個聲音產生固定短句（`--auto`）

固定短句（「連不上主機」「我想想怎麼說比較好」等）是 App 在主機沒回應時也要能播的，而且要和介紹是同一個聲音、同一個語速。
每個要出現在 App 清單上的聲音（資料夾裡有 `voice.toml` 的）都要在**這台**主機上各跑一次，由主機自動試多個 seed、
挑通過驗收且最好的一版；**不要從 M3 或別台機器複製**，在當地重新合成、重新驗收。

```bash
cd ai-tour-guide/host
for voice in <聲音資料夾名稱>…; do        # 每個有 voice.toml 的聲音各跑一次
  uv run python -m buddy_host.speech.phrases --voice "$voice" --auto
done
```

- [ ] 每個聲音都顯示「短句都已準備」，並且在 `~/.buddy-host/out/voice-phrases/<聲音>@<語速>/` 底下有 1、2、3、4、6、7 號的 `.wav`。
- [ ] 某句沒有任何版本通過時，指令會列出那一句並以非 0 結束，那一句不會寫入、該聲音維持「短句未準備」；
      加大 `--max-seeds`（預設 8）並用 `--only <編號>` 只重跑那一句（實測某聲音的 7 號句試到 20 個 seed 才有版本通過）：
      ```bash
      uv run python -m buddy_host.speech.phrases --voice "$voice" --auto --only 2 6 --max-seeds 20
      ```
      試到 20 個還是沒過，那個聲音就維持「短句未準備」（主機照常運作，App 會警示）。
      沒過的版本常見的樣子：短句被生成成 7–10 秒，Whisper 在多出來的雜音上寫出「請不吝點贊訂閱…」之類的幻覺字幕，
      或只聽出開頭一個字。這是真的合成失敗，加 seed 是對的；只差一個字（例如多音字）時要先聽，分辨唸錯還是指標誤判。
- [ ] **試聽 2、3 號句**（開頭是語氣詞「喔」「嗯」，機器驗不準）：通過的版本都在 `<聲音>@<語速>/candidates/<編號>_seed<seed>.wav`。
      採用版本的轉寫在同資料夾的 `index.json`；語氣詞沒被聽出來（例如「喔」寫成「我」、或轉寫沒有「嗯」）的優先聽。
      要換成別的候選，把它複製過去即可（是否已準備只看 `<編號>.wav` 在不在）：
      ```bash
      cd ~/.buddy-host/out/voice-phrases/<聲音>@<語速>
      cp candidates/2_seed99.wav 2.wav && cp candidates/2_seed99.log.json 2.log.json
      ```
      長度明顯比別的聲音長的句子（例如 1 號超過 3 秒）也順便聽一下尾巴。
- [ ] 之後改了某個聲音 `voice.toml` 的 `speed`，那個聲音的短句要重新跑一次（資料夾名稱含語速，語速一變就視為未準備）。
- 這是在本機 GPU 上合成與驗收，不呼叫任何付費 API；每句 8 個 seed，每個都要合成加轉寫驗收，可以放著跑。
  實測每個聲音：M3 約 15–50 分鐘；M6 約 3–6 分鐘（每個 seed 7–10 秒；`--max-seeds 20` 重跑每句約 2.5–3 分鐘），
  四個聲音含重跑約 36 分鐘。
- 人工挑選的舊流程（`python -m buddy_host.speech.phrases` 不帶 `--auto`、`--finalize`、`scripts/install-phrases.sh`）維持原樣，輸出在別的資料夾。

## 8. 真實模式與額度

```bash
uv run python -m buddy_host --max-llm-calls 6
```

- `--max-llm-calls N` 是硬上限，**寫稿和問答共用**，用完就停止準備；每次呼叫都消耗 Claude Pro 額度，所以第一次先用小一點的數字。
- [ ] 第一次跑真實模式前，先用最小請求各試一次（寫稿、一般問答、拍照），確認 `--tools` 旗標和照片的 `Read` 規則在真實 Claude 上可用（見 `host/README.md`「拍照提問」一節，這兩項尚未驗證）。
      這是會耗額度的真實呼叫，先決定次數再做。
- [ ] 啟動後看 `~/.buddy-host/usage.jsonl` 有沒有記錄、`~/.buddy-host/out/reports/` 有沒有用量報告。

## 9. 手機端（在開發用的筆電上做）

不需要在家裡的 Mac 上做，列在這裡是為了一次看完整條流程：

- [ ] 筆電：`cd app && flutter run --release -d <iPhone 的 UDID>`（用 `--release`，debug 版離開 Xcode 後會在背景被中止，驗不了鎖屏）。
- [ ] 首次安裝：手機開啟開發者模式；設定 → 一般 → VPN 與裝置管理，信任開發者憑證。
- [ ] App 設定：主機位址 `http://100.x.y.z:8765`、Token 填第 4 節那組；畫面顯示「主機已連線」。
- [ ] `app/assets/phrases/`（固定短句，被 git 忽略）要在**編譯的那台**筆電上存在；缺了先跑 `scripts/install-phrases.sh`。

## 常見問題

| 狀況 | 可能原因 |
|---|---|
| App 顯示「連不上主機」 | 手機或 Mac 的 Tailscale 沒開；`listen_host` 不是這台目前的 `100.x`；主機沒在跑；Mac 睡著了 |
| App 顯示「token 不正確」 | App 的 Token 和 `config.toml` 的 `token` 不一致（注意前後空白） |
| 主機啟動就報 `listen_host 只能是…` | 填了 `0.0.0.0` 或區網位址；改成 Tailscale 位址 |
| 合成報「找不到參考聲音」 | `~/.buddy-host/voice/<名稱>/` 缺 `ref_24k.wav` 或 `ref_text.txt`；名稱和 `--voice`／`config.toml` 的 `voice` 不一致 |
| Claude 呼叫報找不到 token | `~/.buddy-host/claude-token` 不存在或是空的 |
| 防火牆詢問是否允許連入 | 允許（只有 tailnet 內的裝置連得到）|
