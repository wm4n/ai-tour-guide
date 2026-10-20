# AI Buddy Tour — iPhone App

Flutter App。如何與 Buddy Host 一起啟動、主機位址與 token 怎麼設定，見[頂層 README](../README.md)。

```bash
flutter pub get && flutter analyze && flutter test
```

## 旅程流程（issue #7）

出發後，App 每 10 秒回報位置、行進方向（用前後兩個定位點自己算）與旅人狀態，每 5 秒問主機有沒有新準備好的介紹；
走到景點 150 公尺內、且距離上一段播完至少 3 分鐘才播（`lib/tour/playback_policy.dart`，單元測試在 `test/tour/`）。
播放時其他 App 調小聲，播完釋放 audio session 才會恢復；耳機／鎖定畫面的暫停鍵＝暫停／恢復主動介紹。

開發時可用 `--dart-define=MIN_GAP_SECONDS=20` 縮短兩段之間的最短間隔（預設 180）。

## 問答：按住說話（issue #23）

旅程中畫面有「按住說話」按鈕：**按下**開始聽、**放開**送出（不用等長按判定）。流程：

1. 辨識（`lib/qa/speech_recognizer.dart`）：引擎可注入。`QuestionListener` 先試 iOS **本機** zh-TW（語音不離開手機），
   裝置不支援就改用 **Apple 線上辨識**（語音會送到 Apple），並記住結果、之後不再白試；畫面會標示用的是哪一種。
2. 放開、辨識出字後**立刻**念填空短句（1、2 交替），同時把問題連同位置、行進方向、旅人狀態送給主機（`POST /v1/qa/ask`）。
   「再多說一點」（內含「再多說」「多說一點」等說法）會帶 `more: true`，主機接著剛播完的那段講。
3. 輪詢答案（`GET /v1/qa/answer`）：出現一段就下載一段（`/v1/qa/audio`）、依序播；播放期間其他 App 調小聲，**整個答案播完才恢復**。
   - 問完 8 秒還沒有任何一段：補短句 3（只補一次）；主機說 Claude 在上網查：補短句 4（只補一次）。
   - 額度用完（`failed／quota`）：畫面提示、**不念**；下一次發問會再試。
   - 連不上主機：和旅程輪詢一樣算一次斷線（只念一次短句 6，並退避重試）；主機有回應卻拒絕（401、404…）只在畫面顯示。
4. 問答期間（從按下到答案播完）不開始新的主動介紹；旅程結束時取消進行中的發問。

> 「按下去立刻播短句」我解讀成**放開（問完）之後**才播：按住的時候麥克風是開的，這時候出聲會被辨識進去。這一點要在實機確認；
> 若想改成按下就播，只要把 `QaController._submit` 的 `_say(...)` 移到 `press()`（同時要讓辨識避開喇叭聲）。

**這版還沒做（#24）**：發問時正在播的介紹**不會**暫停、也不會從中斷的那句接著講；目前只是不再開始新的介紹。

### 模擬器沒有麥克風

`--dart-define=FAKE_QUESTION=那間廟拜的是誰` 讓按住說話固定「聽到」這句話（`lib/qa/fixed_question_recognizer.dart`）。
主機用 `--replay-dir` 模式時，問答會回固定的假答案與提示音（不呼叫 Claude）：

```bash
cd host && uv run python -m buddy_host --replay-dir /tmp/some-empty-dir
cd app && flutter test integration_test/qa_flow_test.dart -d <模擬器 UDID> \
  --dart-define=HOST_URL=http://127.0.0.1:8765 --dart-define=FAKE_QUESTION=那間廟拜的是誰
```

實機才驗得到：本機 zh-TW 辨識是否可用、放開後多久拿到最終文字、麥克風權限對話框、播放與錄音切換時的 audio session（#10、#8）。

### 模擬器端到端測試

```bash
# 1. 主機（擇一）。重播模式不呼叫 Claude，只重播 ~/.buddy-host/out/narrations 裡既有的介紹
cd host && uv run python -m buddy_host --replay-dir ~/.buddy-host/out/narrations
#    真實模式每次呼叫 Claude 都耗 Pro 額度，--max-llm-calls 是硬上限（用完就停止準備）
cd host && uv run python -m buddy_host --max-llm-calls 6

# 2. 模擬器：授權定位，設起點
xcrun simctl privacy booted grant location com.wm4n.buddyTour
xcrun simctl location booted set 25.055492,121.51031

# 3. 跑整合測試（它會按「出發」），另開終端機播放 GPX 路線
cd app && flutter test integration_test/tour_flow_test.dart -d <模擬器 UDID> \
  --dart-define=HOST_URL=http://127.0.0.1:8765 --dart-define=MIN_GAP_SECONDS=20 \
  --dart-define=EXPECTED_NARRATIONS=3 --dart-define=WAIT_MINUTES=45
scripts/play-gpx.sh            # 大稻埕（霞海城隍廟）到艋舺（龍山寺），約 3 公里、36 分鐘；--speed 可調
```

模擬器驗不到的：耳機暫停鍵、鎖定畫面、duck 其他 App 的實際聽感，留給實機（#8）。
