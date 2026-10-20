# AI Buddy Tour

陪你出遊的 AI 好友：手動啟動一次後，依位置與時機主動用自然的台灣中文介紹身邊景點；想問時用說的。

- 設計文件：[`docs/superpowers/specs/2026-10-18-ai-buddy-tour-v2-design.md`](docs/superpowers/specs/2026-10-18-ai-buddy-tour-v2-design.md)
- 進度與工單：[GitHub issue #1](https://github.com/wm4n/ai-tour-guide/issues/1)
- v1（Cloud Run + Gemini）已封存在 [`legacy/`](legacy/)，v2 里程碑完成後刪除

## 結構

```
host/     Buddy Host（Python，跑在家中 Mac，只聽 Tailscale 介面）
app/      iPhone App（Flutter）
legacy/   v1 後端與 App，僅供移植時對照
docs/     設計文件、試聽 spike、agent 規則
```

> 這是**公開 repo**：token、主機位址、Tailscale 名稱、參考聲音與其逐字稿一律放在 repo 外（`~/.buddy-host/`），不得提交。

## 開發：同時啟動 Host 與 App

### 1. Buddy Host

需要 [uv](https://docs.astral.sh/uv/) 與 Python 3.12 以上。

```bash
cd host
uv sync
uv run pytest            # 測試
uv run ruff check .      # lint
uv run python -m buddy_host
```

設定放在 `~/.buddy-host/config.toml`（可用環境變數 `BUDDY_HOST_HOME` 指到別處）：

```toml
listen_host = "127.0.0.1"   # 實機請填這台 Mac 的 Tailscale 位址；不接受 0.0.0.0
listen_port = 8765
token = "請自行產生一串隨機字串"   # 可省略，省略則不驗證
```

檢查：

```bash
curl localhost:8765/health                                  # {"status":"ok"}
curl -H "X-Buddy-Token: <token>" localhost:8765/v1/status   # 需要 token
```

### 2. iPhone App

需要 Flutter 3.41 以上與 Xcode。

```bash
cd app
flutter pub get
flutter analyze
flutter test
```

主機位址與 token **不寫在程式碼裡**，兩種給法擇一：

- **App 內設定**：右上角齒輪輸入位址與 token，存在裝置上。
- **第一次啟動的預設值**：把設定寫在 repo 外的 JSON，建置時帶入：

  ```bash
  # ~/.buddy-host/app-defines.json
  # {"HOST_URL": "http://127.0.0.1:8765", "HOST_TOKEN": "<token>"}
  flutter run -d <模擬器或裝置> --dart-define-from-file=$HOME/.buddy-host/app-defines.json
  ```

模擬器可直接連 `http://127.0.0.1:8765`；實機要連主機的 Tailscale 位址（例如 `http://100.x.y.z:8765`）。
App 的 `Info.plist` 已開啟 HTTP 連線（連線走 Tailscale 的 WireGuard 加密，且 MagicDNS 名稱是完整網域，ATS 預設會擋）。

畫面中央的晶片顯示「主機已連線／主機未連線」，只有已連線時「出發」才可按。
