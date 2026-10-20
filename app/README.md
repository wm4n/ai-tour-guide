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
2. **放開的當下**就念填空短句（1、2 交替）——不等辨識的最終結果（最久要等幾秒）；麥克風已經停了，不會錄到短句。
   辨識出字後把問題連同位置、行進方向、旅人狀態送給主機（`POST /v1/qa/ask`）。聽不到字就只在畫面提示。
   「再多說一點」（內含「再多說」「多說一點」等說法）會帶 `more: true`，主機接著剛播完的那段講。
3. 輪詢答案（`GET /v1/qa/answer`）：出現一段就下載一段（`/v1/qa/audio`）、依序播；播放期間其他 App 調小聲，**整個答案播完才恢復**。
   - 問完 8 秒還沒有任何一段：補短句 3（只補一次）；主機說 Claude 在上網查：補短句 4（只補一次）。
   - 額度用完（`failed／quota`）：畫面提示、**不念**；下一次發問會再試。
   - 連不上主機：判斷與旅程輪詢一致——除了 404（主機已經沒有這題，只在畫面提示）以外的失敗都算斷線（只念一次短句 6，並退避重試）。
4. 問答期間（從按下到答案播完）不開始新的主動介紹，旅程結束時取消進行中的發問。
5. **發問時正在播的介紹會先停下**（按下的當下），答完（或這題失敗、取消）後**從被打斷那一句的開頭接著播**，只播剩下的部分
   （`lib/tour/resume_point.dart`）：
   - 主機在每段介紹的資訊裡附 `unit_starts`（各句＝合成單位的起點秒數；從 wav 裡單位之間的靜音偵測，快取命中的舊介紹也有）。
   - 起點是「合成單位」（語音管線的一個 chunk）：通常一句，但很短的句子會併在同一個單位，被打斷在併起來的短句中間時會回到那一組的開頭。
   - 被打斷的位置落在某個單位前面的靜音（管線預設 0.45 秒起）裡，等於剛好在句界，從下一個單位開始；主機沒給 `unit_starts`（舊主機）就從被打斷的位置接。
   - 被打斷時不釋放 audio focus（接著要念短句、播答案，其他 App 的音量不要中間跳回來）；接續播完才釋放。
   - **接續播完才回報「講過」**；中途被打斷、或結束旅程時被停掉的都不算。使用者按了暫停鍵時，答完不會自己接著講，等他按繼續。

> issue 寫「按下去立刻播短句」，我做成**放開（問完）的當下**：按住的時候麥克風是開的（`speech_to_text` 用 playAndRecord、
> 沒有回音消除），這時出聲會被辨識進去；而且短句內容（「好，我來查一下」）是對問題的回應，使用者還沒問完就播不通。
> 若真的要按下就播，要先處理辨識會錄到喇叭聲，以及短句播完釋放 audio session 會中斷錄音的問題。

取消（旅程結束、手指被系統奪走）時會停掉答案與短句的播放，並釋放 audio focus 讓其他 App 的音量恢復。

## 拍照提問（issue #11）

旅程中按「拍照問」：開系統相機拍一張 → 讀指南針 → 立刻念填空短句 → 把照片、位置、**指南針方向**送給主機
（`POST /v1/qa/ask-photo`，問題固定是「這是什麼？」）→ 之後和按住說話一樣聽答案（短句、逐段下載、額度與斷線的處理都相同）。

- 拿著手機拍照時，「眼前、左右」以**指南針**（手機背面對著的方向，`flutter_compass` 的 `headingForCameraMode`）為準，
  不是走路的方向；讀不到指南針就不帶方向（主機會明說方向不明），不拿走路的方向冒充。
- 照片縮到長邊 1600 像素、JPEG 品質 80 再上傳到你家中的主機；主機只存在本機、保留 24 小時（見 `host/README.md`）。
  **但主機會請 Claude 看這張照片，所以影像會送到 Anthropic**（和問答的文字一樣走你的 Claude Pro 訂閱）。
- 使用者取消拍照：安靜結束，暫停的介紹接著播；拍照時正在播的介紹會先停下（和發問相同）。
- 模擬器沒有相機與指南針：`--dart-define=FAKE_PHOTO=true` 固定「拍到」一張小圖、朝向西方。

```bash
cd host && uv run python -m buddy_host --replay-dir /tmp/some-empty-dir
cd app && flutter test integration_test/photo_flow_test.dart -d <模擬器 UDID> \
  --dart-define=HOST_URL=http://127.0.0.1:8765 --dart-define=FAKE_PHOTO=true
```

注意：`flutter test` 每次都會重新安裝 App，**定位權限會被重設**；要在測試期間持續授權
（`xcrun simctl privacy <UDID> grant location com.wm4n.buddyTour`），不然「出發」會卡在權限對話框。
模擬器若跳出 Apple 帳號驗證等系統對話框，改用一台沒登入帳號的新模擬器（`xcrun simctl create`）。

實機才驗得到：真的相機與權限對話框、指南針讀數的準確度、Claude 看圖回答得對不對（須使用者先同意呼叫次數）。

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
