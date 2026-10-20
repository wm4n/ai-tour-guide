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
