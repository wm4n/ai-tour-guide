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
git clone git@github.com:wm4n/ai-tour-guide.git
cd ai-tour-guide/host
uv sync --group speech      # 含 torch、KittenTTS 2、Whisper，約數 GB，要一段時間
uv run pytest -q            # 全綠才往下（不需要 GPU 或網路以外的東西）
```

- [ ] `uv sync --group speech` 成功。
- [ ] `uv run pytest -q` 全過。
- [ ] 第一次真正合成時會下載 KittenTTS 與 Whisper 的模型（Whisper 存在 `~/.buddy-host/cache/`），這台 Mac 需要能連外網；
      建議先跑一次語音合成確認（見第 6 節）。

## 4. 機密與設定（`~/.buddy-host/`，不入 repo）

```bash
mkdir -p ~/.buddy-host/voice/F2
chmod 700 ~/.buddy-host
```

- [ ] **Claude token**：在這台 Mac 上執行 `claude setup-token`（需要 Claude Pro 訂閱），把印出的 token 存成
      `~/.buddy-host/claude-token`，權限 `chmod 600`。建議在這台重新產生，不要從別台複製。
- [ ] **參考聲音**：把 `ref_24k.wav` 與 `ref_text.txt`（逐字稿，缺了會直接報錯）放進 `~/.buddy-host/voice/F2/`。
      這兩個檔不入 repo，用隨身碟或 AirDrop 從原本的機器搬；搬完刪掉中間的副本。
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

## 7. 真實模式與額度

```bash
uv run python -m buddy_host --max-llm-calls 6
```

- `--max-llm-calls N` 是硬上限，**寫稿和問答共用**，用完就停止準備；每次呼叫都消耗 Claude Pro 額度，所以第一次先用小一點的數字。
- [ ] 第一次跑真實模式前，先用最小請求各試一次（寫稿、一般問答、拍照），確認 `--tools` 旗標和照片的 `Read` 規則在真實 Claude 上可用（見 `host/README.md`「拍照提問」一節，這兩項尚未驗證）。
      這是會耗額度的真實呼叫，先決定次數再做。
- [ ] 啟動後看 `~/.buddy-host/usage.jsonl` 有沒有記錄、`~/.buddy-host/out/reports/` 有沒有用量報告。

## 8. 手機端（在開發用的筆電上做）

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
| 合成報「找不到參考聲音」 | `~/.buddy-host/voice/F2/` 缺 `ref_24k.wav` 或 `ref_text.txt` |
| Claude 呼叫報找不到 token | `~/.buddy-host/claude-token` 不存在或是空的 |
| 防火牆詢問是否允許連入 | 允許（只有 tailnet 內的裝置連得到）|
