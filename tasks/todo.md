## Review - Background Tour Playback

- Design: `docs/superpowers/specs/2026-06-11-background-tour-playback-design.md`
- Plan: `docs/superpowers/plans/2026-06-11-background-tour-playback.md`
- OpenSpec change: `openspec/changes/background-tour-playback`
- Verification:
  - `cd flutter_app && flutter analyze`
  - `cd flutter_app && flutter test test/unit/settings_provider_test.dart`
  - `cd flutter_app && flutter test test/unit/tour_playback_queue_provider_test.dart`
  - `cd flutter_app && flutter test test/unit/trigger_provider_test.dart`
  - `cd flutter_app && flutter test test/unit/session_provider_test.dart`
  - `cd flutter_app && flutter test test/unit/narration_provider_test.dart`
  - `cd flutter_app && flutter test test/unit/notification_service_test.dart`
  - `cd flutter_app && flutter test test/widget/narration_mini_bar_test.dart`
  - `cd flutter_app && flutter test test/widget/narration_sheet_test.dart`
  - `cd flutter_app && flutter test test/widget/settings_screen_test.dart`
- Manual Android verification still required on a device for locked-screen background playback, foreground service notification coexistence, and media controls.

## Review - Android Desugaring Build Fix

- Fixed `:app:checkDebugAarMetadata` failure from `flutter_local_notifications` by enabling core library desugaring in `flutter_app/android/app/build.gradle.kts`.
- Verification:
  - `cd flutter_app && flutter build apk --debug --dart-define-from-file=dart_defines/dev.json`

## Review - Android Geolocator Wake Lock Permission Fix

- Fixed geolocator background updates failing to open the Android event stream because `ForegroundNotificationConfig(enableWakeLock: true)` requires `android.permission.WAKE_LOCK`.
- Updated `openspec/specs/background-location/spec.md` so the background location manifest contract includes `WAKE_LOCK`.
- Verification:
  - `cd flutter_app && flutter test test/unit/android_manifest_test.dart`
  - `cd flutter_app && flutter analyze`
  - `cd flutter_app && flutter build apk --debug --dart-define-from-file=dart_defines/dev.json`

## Review - v2 第一階段（`/implement`，issue #1，2026-10-19）

範圍：不需要人類介入就能完成的 `ready-for-agent` 票（#2 → #3、#4 → #6、#16），#5 只產生候選並等挑選。
分支 `feat/v2-buddy-tour`；已通過機密掃描並 push（2026-10-19）。

### 狀態
| 票 | 狀態 | 備註 |
|---|---|---|
| #2 專案骨架 | 已關閉 | 實機（Tailscale）尚未驗證，留給 #15 |
| #3 Claude Code 介接層 | 已關閉 | 冷啟動約 3 秒、可讀圖、可呼叫本機 MCP；`utilization` 在 `unifiedWindows` 底下；每次新對話約 25k 輸入 token |
| #4 語音管線 | 已關閉 | 名花之里原稿 159 秒、10 段全過、RTF 4.44 |
| #16 語助詞 | 已關閉 | CER 量不出粵語腔；啊／喔／吧／一下下仍避免，待人耳確認 |
| #5 固定短句 | 已關閉 | 6 句（5、8 已取消）挑好並裁好；App 播放機制完成 |
| #6 景點準備 | 已關閉 | 真實執行完成；問題已修；開場句：城隍廟驗證通過，李臨秋故居以個性規則預防、尚未用真實 Claude 重寫驗證 |

### 使用者已同意／已決定（不要重問）
- Haiku 4 次（#3 探測）：已用完。Sonnet 2 次（#6 真實執行）：已用完；之後任何 Claude 呼叫都要重新取得同意
- 開場句驗收不過：選 **A**（多試 seed，不呼叫 Claude）
- 固定短句 5（額度用完）改成畫面提示、8（恢復）改成自動繼續，**都不念**；剩 6 句
- 挑選：1→seed42、2→seed42、3→seed99、4→seed42、6→seed2026、7→seed1234；成品在 `~/.buddy-host/out/phrases-final/`，**不入 repo**（公眾人物聲音的複製），用 `scripts/install-phrases.sh` 複製進 `app/assets/phrases/`（被 git 忽略）
- 用語：做兩岸用語詞表並由程式檢查（`host/config/taiwan_terms.json`）；固定短句的用語建議已貼在 #5，使用者回覆「不用念」所以不再改字
- Push：**先掃描機密再 push**（掃描方式：整段 `git log -p 86636e9..HEAD -- . ':!legacy'` 找 token／IP／ts.net／/Users/，再用真實 token 與參考逐字稿反向比對整個歷史，只輸出計數）

### 待辦
1. 使用者聽 `~/.buddy-host/out/narrations-fixed/`（接縫套了新裁切）確認接縫雜音是否消失；以及 `~/.buddy-host/out/particles-listen/` 確認啊／喔／吧／一下下的口音
2. 下次取得 Claude 授權時，重寫李臨秋故居稿子，驗證新規則（第一句不以專有名詞開頭）讓開場句通過
3. 記憶體：#6 的結論不是乾淨量測（基準已用 13 GB、swap 峰值 23 GB），乾淨環境與 M6 要重量

### 試聽回饋後的調整（2026-10-19～20）
- 評分：88 → **90**（朋友式口吻稿＋段落停頓＋差一點就收下）。使用者說「講得真的不錯了」，偶爾字音不準可接受
- 做了：段落停頓（空行 1.0 秒、單位接縫 0.45 秒）、旅人即時狀態 `TravelerContext`、個性檔朋友式口吻、同音字統一（隍／黃、它／他）、差一點就收下（`approx_cer` 0.10、`leaf_approx_cer` 0.25）
- 不採用：KittenTTS 2 的 `<pause>`／`[情緒]`／`(((強調)))`（`docs/spikes/2026-10-19-tags/`）；虛構「朋友來過」
- Claude 用量：Sonnet 5.5 共 3 次（城隍廟：走路獨自、帶小朋友、開車），使用者已同意「可以測試幾次」，**之後的呼叫仍要先講次數**
- 待辦：問答模式（放寬重試）先不做，使用者聽完再說；開車時是否縮短目標秒數：使用者說不用；稿子事實核對：目前只是測試語音，**不需要**（使用者 2026-10-20 確認），正式給人用之前再做；App 要在哪裡選同行者留給 #7

### 下一步：#7（第二階段起點，2026-10-20）
- 使用者要在 `/clear` 後輸入 `/implement #7`（`/implement` 只能由使用者輸入，我不能用 Skill 工具啟動）
- 先讀：issue #7、設計文件第 6.1.1、7、13 節、本節、`app/lib/host/host_connection.dart`、`host/src/buddy_host/narration/{preparer,traveler}.py`
- 主機端已就緒：`AreaPreparer.prepare(location, traveler=TravelerContext(...))`；App 端要新做：位置與即時狀態回報、主機通知、下載播放、時機規則（兩段至少隔 3 分鐘）
- 需要同意才能做：真實 Claude 呼叫（先講次數）、實機（#8）；模擬器 GPX 路線要放進 repo
- 品質基準：語音約 90 分，不必追求完美；停頓、朋友式口吻、`approx` 規則都已完成

### #7 App 走一趟（`/implement #7`，2026-10-20）

做了：
- 主機：`/v1/tour/{start,location,end}`、輪詢 `/v1/tour/narrations?after=`、下載 `/v1/tour/audio?id=`；`TourSession`（同時只準備一次、期間只留最新位置、移動 250 公尺或旅人狀態改變才重準備）；`BudgetedLlm` 硬上限（`--max-llm-calls`）；`ReplayPreparer`（`--replay-dir`，不呼叫 Claude）；`PreparedNarration` 帶座標
- App：`PlaybackPolicy`（150 公尺內、間隔 3 分鐘可用 `MIN_GAP_SECONDS` 調整、暫停／播放中不開始、走遠 500 公尺或放 30 分鐘就丟）、`TourController`、自己用前後定位點算方向、duck＋播完釋放 audio session、耳機鍵＝暫停／恢復主動介紹、出發前選旅人狀態、Info.plist 背景定位與音訊
- `scripts/gpx/dadaocheng-to-bangka.gpx`（霞海城隍廟→龍山寺，3.0 公里，OSM 步行路網）、`scripts/play-gpx.sh`、`app/integration_test/tour_flow_test.dart`

驗證：host 369 項、app 102 項、ruff／analyze 乾淨。模擬器（乾淨的 iPhone 16／iOS 18.6，已刪除）以重播模式實跑：出發→主機通知→下載→自動播出「台北霞海城隍廟」；1 分鐘內位置回報 5 次。

**還沒驗證（誠實列出）**
- 驗收「整趟至少 3 段」「兩段間隔 ≥ 3 分鐘」的真實一趟：需要 Claude 呼叫，**尚未取得授權**。預估：起點 1 次準備 ＋ 約 12 次重準備（3 公里 ÷ 250 公尺）＝ 最多約 13 次 × 每次最多 2 景點（快取命中不重寫）≈ 最多 26 次 Sonnet；建議 `--max-llm-calls 10` 先跑。M3 合成很慢（單段數分鐘），GPX 要用 `--speed 1.4`（約 36 分鐘）而不是快轉；跑之前先確認沒有其他大型程式
- 耳機／鎖定畫面暫停鍵、duck 其他 App 的實際聽感、鎖定畫面時的背景定位與播放、`TourAudioHandler` 在「沒有音訊在播」時 iOS 是否仍把遙控鍵交給 App：模擬器沒有耳機鍵，留給 #8 實機
- 「額度用完」只在畫面提示；連不上主機時播固定短句 6、自動繼續：不在 #7 範圍，未做
- 準備中途按「結束」：`asyncio.to_thread` 裡的合成無法取消，舊的合成會跑完（GPU 短暫被占用）

**真實模擬跑（2026-10-20 02:36，使用者同意 Claude 上限 10 次，實際用 2 次 Sonnet）— 未達「整趟 3 段」**
- 路線以 1.4 公尺/秒播放，M3 在 swap 吃緊（已用 17 GB）下，起點周邊兩段（約 105 秒音檔）合成花 21、29 分鐘；第一段 02:57 好、整批 03:05 才通知，人早已走到艋舺附近，兩段都被「走遠 500 公尺」規則丟棄（規則正常運作）
- 結論：**在這台機器目前的狀態下，準備速度（約 10～15 分鐘一段）趕不上步行**，與設計文件 §16「M3 撐不住就等 M6 驗收」一致。修了「做好一段通知一段」（`on_ready`），但不能解決合成本身的速度
- **使用者決定（2026-10-20）：選③，「整趟 3 段」留到 M6 再驗**；#7 其餘驗收條件已完成。以下為當時列的選項：①先重開機清 swap，關掉大型程式後再跑（乾淨環境 RTF 約 4～5，一段約 4 分鐘），②把 GPX 速度降到 0.3～0.5 公尺/秒當桌上驗證（驗證流程，不是真實速度），③等 M6。快取裡已有這次的兩段（`~/.buddy-host/out/narrations/osm_way_*`），同一旅人狀態再跑會直接命中、不耗 Claude

`/code-review` 後已修：暫停時沒釋放 audio session（其他 App 一直被壓低）、載入音檔期間按暫停會照播、準備失敗後 250 公尺內不重試（改為冷卻 60 秒後重試）、用不到的 `narrating` 參數。
審查指出但**刻意不改**（之後視實測再決定）：
- 額度（`quota`）停止後不會自動恢復，只能結束再出發；設計文件 §11 的 `resetsAt` 自動繼續不在 #7 範圍
- App 以 500 公尺丟棄過期介紹，開車或準備太久時景點到貨已走遠會被丟（`_seen` 已記錄，不再補下載）；實測後再調 `staleDistanceM`
- 狀態改變時，已發佈的景點不會用新狀態重寫（`exclude_ids`）；只有前方新景點用新狀態
- 固定短句播放完會釋放 audio session，若剛好有主動介紹在播可能提早釋放（極少見）
- `--max-llm-calls` 是新增的硬上限，與「不設每趟用量上限」的偏好不同：預設不啟用真實準備，要明確指定次數才跑；用量仍由 `usage.jsonl` 記錄
- 平台殼層（`JustAudioNarrationPlayer`、`GeolocatorLocationSource`、`build_real_preparer`）沒有單元測試，由模擬器整合測試與 #8 實機覆蓋

踩到的坑：
- `simctl privacy grant location` 要在 App 已安裝後才有效，而 `flutter test` 每次重裝都會重置權限；整合測試期間要用迴圈持續授權，否則系統對話框會蓋住 App
- `just_audio` 只啟用 audio session 不停用：不主動 `setActive(false, notifyOthersOnDeactivation)`，其他 App 會一直被壓低音量（短句播放器原本也有這個問題，已補）
- 選項回呼若用 build 時的狀態，連續快速點選會互相覆蓋（旅人選擇器，測試抓到）

### 下一步：#14 → #13 → #9（不需要實機，2026-10-20）

- 使用者要在 `/clear` 後輸入 `/implement #14`，完成後再 `/implement #13`、`/implement #9`（一次一張）
- **#13、#14 的 issue 內文過時**：寫「播放『額度用完了…』」「播放『我恢復了…』」，但短句 5、8 已取消（設計文件 §9.3、§11、§12）。**以設計文件為準**：額度用完只在畫面提示、不念；恢復或重新連上後自動繼續、不念；連不上主機才播短句 6（App 已有 `FixedPhrase.hostUnreachable`）。我嘗試更新 issue 內文被權限擋下，尚未更新，需要使用者自己改或授權
- 先讀：issue、設計文件 §7、§9.3、§11、§12、§13、本節、`app/lib/tour/tour_controller.dart`、`host/src/buddy_host/tour/session.py`
- #7 留下、這三張會接手的缺口：額度（`quota`）停止後 `TourSession` 不會恢復（#13）；輪詢失敗只 `debugPrint`、沒有「斷線只提示一次、退避重試、連上後不重播」（#14）；`--max-llm-calls` 的 `llm_budget` 停止**不應**自動恢復
- 驗收方式：#14、#13 用 fake 時鐘／模擬事件做單元測試，再用模擬器關掉主機驗一次（做法見 `app/README.md`「模擬器端到端測試」；`simctl privacy grant location` 要在 App 安裝後、且要持續授權）。#9 單元測試不需要 Claude；「GPX 重播驗證好友會引用剛去過的地方」要真實呼叫 Claude，**先跟使用者講次數**
- 不需要實機：#8、#15、#17；#12 要使用者的 Google API key（可能計費）；#10、#11 另議

### 踩到的坑
- **逐句合成會誤判**：兩個字的「哇！」四個 seed 的 CER 都 ≥ 1；管線改成先併段（約 90 字），整段失敗才往下拆（段 → 句 → 分句）
- **SSL**：python.org 版 Python 的 urllib 不認這台機器的憑證，用 `truststore`
- **MPS 的記憶體數字不可信**：`ps` 的 RSS、`/usr/bin/time -l` 都失真，改量系統層（vm_stat + swap）
- **公共 Overpass 常過載**：多鏡像站換站，整個失敗就降級為只用維基座標搜尋
- **真實資料才暴露的排序問題**：行政區標籤、街邊設施（YouBike）、同名重複，已排除
- **個性檔的範本比規則更有力**：範本若示範「哇！」Claude 就會照做；有測試守住
- **驗收的盲點（使用者試聽才發現）**：Whisper 常把句首語助詞與前導聲音當雜音省略，CER 照樣是 0。每個合成單位開頭有一小段 -25～-33 dB 的聲音，接著近乎靜音，約 0.45 秒才開口；Whisper 時間戳記抓不到，改用能量判斷開口點（`speech/onset.py`）
- **「額度」TTS 念不出來**：被念成「眾珠／過煮／夠度」，CER 0.083～0.167 仍過 0.2 門檻，所以短句（≤20 字）門檻收緊到 0.05
- **稿子開頭被整句跳過**：城隍廟前兩句（含廟名）、李臨秋故居第一句連換 4 個 seed 都驗收不過被丟掉。多試 6 個 seed 仍全滅，真正原因：(1) Whisper 把罕用字「隍」寫成同音的「黃」、「它」寫成「他」，短句門檻 0.05 下錯一個字就不過 → CER 把同音寫法視為相同後，城隍廟開場句第 2 個 seed 通過（CER 0）；(2) 「李臨秋」是罕用人名又在冷啟動的句首，真的唸不準（「李丁秋」）→ 個性檔規定第一句不以專有名詞開頭
- **機器記憶體吃緊**：開跑前系統已用 13 GB，swap 近滿，真實執行花了 60 分鐘（RTF 31～58）。**跑語音之前先確認沒有其他大型程式**
- **兩岸用語詞表不能太貪心**：「登錄」是台灣文資正規用語，誤判後已移除；詞表只抓字詞，抓不到語氣或腔調
- Sonnet 寫的稿比規定長（234、267 字；規定 130～200 字），李臨秋故居 50 秒（目標 30～45 秒）
- 模擬器上有 Apple ID 驗證的系統對話框會蓋住 App；改建乾淨的模擬器驗證，驗完刪除
- 全域規則：**所有回覆用繁體中文**（中途有幾輪誤用簡體，已修正）

### 接續指令
```bash
cd host && uv run pytest && uv run ruff check .        # 300 項
cd app && flutter analyze && flutter test              # 26 項
scripts/install-phrases.sh                             # 把 6 句複製進 App（被 git 忽略）
tail -f /private/tmp/claude-503/*/scratchpad/opening.log   # 開場句驗證進度
```

### #14 連不上主機時的處理（`/implement #14`，2026-10-20）

做了（App 端，主機不用改）：
- `HostReachability`（`app/lib/tour/host_reachability.dart`）：記連線狀態與退避（10、20、40、60 秒封頂），只在一次斷線的第一次失敗回報「新斷線」
- `TourController`：輪詢失敗＝斷線，念一次短句 6（`FixedPhrase.hostUnreachable`）；等到沒有介紹在播、沒暫停才念，念的當下不同時開始介紹；連上後安靜繼續、不念、不重播（`_seen`＋游標）；斷線期間不回報位置，連上後補報最新位置；輪詢不重疊
- 輪詢成功後下載失敗：算一次斷線，介紹留在佇列，主機回來後補抓（原本會永久遺失）

驗證：app 119 項、host 372 項、analyze 乾淨。**沒有跑模擬器關主機的端到端**（單元測試用 fake 時鐘涵蓋流程；HTTP 失敗轉成 `TourApiException` 由 `tour_api_test` 涵蓋）。

審查指出但刻意不改：
- HTTP 非 2xx（例如 401 token 錯）也當斷線念短句 6；畫面上的連線 chip 已會顯示「token 不正確」
- 下載一直 404（主機快取被清）也會被當斷線、在退避下重試，直到介紹過期（500 公尺／30 分鐘）才丟
- `_report`、`_restartOnHost` 失敗不計入連線狀態，以輪詢為心跳
- 畫面 chip（`connectionProvider` 自己每 5 秒檢查）與控制器的連線判斷是兩套，短暫不一致可接受
- issue #14 內文仍寫「我恢復了，我們繼續」，以設計文件為準（恢復不念）

### #13 額度用完與用量報告（`/implement #13`，2026-10-20）

issue 內文過時（同 #14）：以設計文件為準，額度用完與恢復都**不念**，只有畫面提示。

做了：
- 主機：`QuotaExceededError.resets_at`（取被拒絕事件的 `resetsAt`，epoch 秒）；`TourSession` 額度停止後，App 下一次回報位置時若已過 `resetsAt` 就以**最新位置**重新準備（不走 250 公尺規則），這次準備就是探測，仍被拒絕就依新的 `resetsAt` 再停；沒有 `resetsAt` 或已過期的值，隔 15 分鐘再試；`llm_budget`／`forbidden_model` 不自動恢復
- 用量報告：`tour/usage_report.py` 從 `usage.jsonl` 篩出本趟呼叫，寫 `~/.buddy-host/out/reports/tour-<開始時間>.json`（每次呼叫的用途、模型、時間、token、5 小時／7 天視窗 utilization、是否撞上限；totals 含各模型次數與用量、utilization 首末差）；`POST /v1/tour/end` 回傳 `summary`；報告失敗只記 log、不讓結束失敗
- App：`TourApi.end` 回傳 `TourSummary?`，結束畫面 `TourSummaryCard`（介紹段數、時間、Claude 呼叫次數、兩個視窗用量與本趟增加、是否撞到上限）；下一趟出發清掉；額度提示在主機恢復後隨輪詢自動消失

驗證：host 397 項、app 127 項、ruff／analyze 乾淨；全程用 fake，**沒有呼叫真實 Claude**。真實事件形狀已用 `~/.buddy-host/usage.jsonl` 的實際紀錄對過（`utilization` 在 `unifiedWindows` 底下、0～1 比例、`resetsAt` 是 epoch 秒）。**沒有驗證**：真的撞到額度時 `status=rejected` 事件的 `resetsAt` 是否在頂層（只有 `allowed` 的真實樣本）；模擬器端到端。

審查指出但刻意不改：
- 恢復時 `stopped_reason` 立刻清掉，若仍被拒絕，App 的提示會閃一下又出現（resetsAt 已知時很少發生）
- 只有 App 回報位置時才檢查恢復（App 不回報就沒有要準備的位置）
- `usage.jsonl` 的 `timestamp` 是呼叫完成時間，跨越出發／結束邊界的呼叫以完成時間為準；結束時還在跑的呼叫會被取消、不入報告
- 「用量變化」不含第一次呼叫本身的消耗
- `--max-llm-calls` 是既有的每行程開發保護，不是每趟上限；是否拿掉由使用者決定
- 問答（暫停問答）尚未實作，這張只涵蓋主動介紹的停止

### #9 旅程記憶（`/implement #9`，2026-10-20）

做了：
- 主機 `tour/journey.py`（`JourneyMemory`）：一趟的範圍（沒按結束、距上次活動不到 2 小時再出發＝接續；否則新的一趟，被丟下的舊趟先寫完用量報告）；這趟去過的地方；跨趟永久記錄講過的景點與稿子（`~/.buddy-host/journey.json`，原子寫入、壞檔改名留存、寫不進去只記 log）；`recent_topics`（這趟最近 5 個地方名）與 `told_before`（每個地方最近 2 次講過的稿子、各截 300 字）有上限
- **「講過」以 App 播完為準**：新增 `POST /v1/tour/played`（不認得的 id 回 200 並忽略）；App 播到最後才回報，送不出去的留著、輪詢連上後補送、最多留 20 筆；被丟掉（走遠／放太久）、結束時被打斷的都不算
- 接上寫稿：`TourSession` 每次準備都帶 `exclude_ids`（含這趟已講過）、`recent_topics`、`told_before`；快取指紋加入 `recent_topics`；`ReplayPreparer` 收下並忽略新參數；`--replay-dir` 不寫 `journey.json`
- `/v1/tour/start` 回應 `resumed`；接續時用量報告涵蓋整趟

驗證：host 422 項、app 133 項、ruff／analyze 乾淨；全程 fake，沒有呼叫真實 Claude。

**還沒做（誠實列出）**
- 驗收「GPX 重播驗證好友會引用剛去過的地方」與「再次經過時稿子明顯換角度」：要真的呼叫 Claude。建議只驗稿子、不合成（合成趕不上步行，見 #7）：用 `build_script_request`＋`ClaudeCliClient`，介紹 A → 帶 `recent_topics=[A]` 寫附近的 B → 帶 `told_before` 再寫一次 A，`max_rewrites=1` 最多 3～6 次 Sonnet。**先跟使用者講次數、取得同意再跑**
- 快取影響（要告訴使用者）：同一條路線重跑不再保證命中舊稿（稿子可能寫「剛剛的 A」）；起點那段仍可命中。每播完一段，之後新準備的稿子都會重寫＝耗額度

審查指出但刻意不改：
- 主機重啟後，App 補送的播完回報會被當未知 id 丟掉（`_published` 只在記憶體；要持久化已發佈稿子才能解，目前不值得）；`end()` 之後才到的回報同理
- 用量報告段數口徑：被丟下的舊趟用「播完數」，`end()` 用「本次發佈數」，接續後會少算；被丟下的舊趟沒有 `stopped_reason`
- `touch` 最多落後 60 秒才存檔；系統時鐘回撥會被當成接續
- 只記「播完的景點」，不記實際走過的位置；「必要時才跳過」（設計文件 §7.6）沒做，一律換角度再講
- `recent_themes`（排序避免重複主題）issue 沒要求，未接
- 巢狀 dict 的 `_visited`、`JourneyMemory` 的可調參數維持簡單，不拆 dataclass／儲存層

### PR #18 review 的兩則建議（2026-10-20）
- App：下載回 404（主機已沒有這段，例如主機重啟）改為丟掉、不重試、不算斷線；`TourApiException` 帶 `statusCode`，連不上、逾時、5xx 仍照斷線處理
- 主機：`finish_tour`（讀整份 `usage.jsonl`）改用 `asyncio.to_thread`，`/v1/tour/start`（替被丟下的舊趟收尾）與 `/v1/tour/end` 都不再卡住事件迴圈
- 驗證：host 424 項、app 137 項、ruff／analyze 乾淨

## #20 問答（主機）：文字問答直通（2026-10-20，分支 `feat/v2-qa`）

做了：
- `POST /v1/qa/ask`（問題＋位置、行進方向、旅人狀態，`more` 表示「再多說一點」）回 id；`GET /v1/qa/answer?id=` 輪詢 `status`（answering／done／failed）、`text`、`searching_web`、`reason`（quota／llm_budget／forbidden_model／error）
- `qa/prompt.py`：個性檔後面接問答專用指示；prompt 帶附近最多 5 個景點（維基摘要截 200 字）、這趟剛講過的、這些景點以前講過的（沿用 #9 上限）；`more` 時帶 `JourneyMemory.last_told()`（只算 App 回報播完的）
- 問答固定 Sonnet、每次新對話；用量記錄沿用 `ClaudeCliClient`（`purpose=qa`）；Fable 由既有 `modelUsage` 檢查擋下
- `ClaudeCliClient`／`BudgetedLlm` 新增 `on_tool`：`content_block_start` 與 `assistant` 兩處的 tool_use 以 id 去重；`WebSearch`／`WebFetch` → `searching_web`
- 抽出 `llm.quota.QuotaGate`：旅程準備與問答共用，任一邊撞到額度兩邊一起停；到恢復時間後下一次呼叫即探測。`TourSession.stopped_reason` 改為 property（額度看閘門）
- `AreaPreparer.nearby()`：與 `prepare` 同一組快取查詢範圍；寫稿與問答共用同一個 `BudgetedLlm`（`--max-llm-calls`）；重播模式問答回 503

驗證：host 498 項、ruff 乾淨；全程 fake LLM／假 `claude` 行程，**沒有呼叫真實 Claude**。

code-review 後修正：
- 競態：旅程被額度閘門擋下後，若問答先在恢復後把閘門打開，旅程要等人走滿 250 公尺才會補準備 → `_run` 被擋下時忘掉錨點（有測試）
- `report()` 的死條件；`_tool_use` 無 id 時的去重 key

審查指出但刻意不改：
- 連續發問不去重、不限併發（每題一次 Claude 呼叫）：#22 會處理 GPU 排程；是否要限制再看實測
- `failed／quota` 不帶恢復時間（App 只要畫面提示，沒要求顯示何時恢復）
- `llm_budget` 不進共用閘門（用盡就是用盡，不會恢復；問答會多走一趟 `BudgetedLlm` 才失敗，無害）
- 例外階梯（Budget → Quota → Forbidden）在 session 與 QaService 各一份、`TourFix` 的匯入方向、`model="sonnet"` 與預設值重複（刻意明確釘住）：判斷題，未重構

**還沒做**：真實 Claude 驗證（問答品質、`searching_web` 真實事件）——要使用者先同意次數。

## #21 問答（主機）：答案語音分段合成與逐段驗收（2026-10-20，分支 `feat/v2-qa`）

做了：
- `qa/segmenter.py`（`AnswerSegmenter`）：串流文字寫完一句就切；第一段盡量短（太短併下一句；第一句超過 40 字在第一個夠長的逗號先切）；之後約 60 字一段
- `QaService`：寫到哪切到哪，一段一段交給 `SpeechPipeline`（驗收、換 seed、拆句、跳過的規則與主動介紹完全相同）；做好的段落出現在 `answer.segments`，`GET /v1/qa/audio?id=&index=` 下載；被跳過的不佔編號；全被跳過回 `failed／no_audio`
- 「收到問題 → 第一段可下載」每題記一筆到 `qa-latency.jsonl`，用量報告新增 `qa`（次數、平均、最大）；App 的結束摘要沒動
- 上網前的開場白不念（指示 Claude 不要先說＋丟掉還沒吐出的文字）
- 介紹與問答共用語音管線，以 `SerializedSpeech`（鎖）輪流使用

驗證：host 540 項、ruff 乾淨；合成器、辨識器、Claude 全是 fake（含一組用真的 `SpeechPipeline` 搭假引擎的測試）。**沒有呼叫真實 Claude／合成。**

code-review 後修正：
- 無標點或超長的第一句：第一段會拖到整個答案寫完 → 在逗號先切（有測試，含逐字串流與一次餵完結果一致）
- 取消與殘留：`_answer` 被取消時合成任務會洩漏、答案失敗或被淘汰後排隊的段落還會合成／補寫檔 → `try/finally` 收掉任務、`_synthesize` 先確認答案仍在進行；`_record_latency` 的例外不再卡住答案
- `SerializedSpeech` 搬到 `speech/serialized.py` 並補測試

審查指出但刻意不改：
- 問答還不會插隊（`SerializedSpeech` 的鎖不保證順序）：#22
- 失敗的答案已做好的段落仍可下載（由 App 決定要不要播）；延遲只記有第一段成功的問答（失敗的不進平均）
- 開場白超過 10 字且在上網前已吐出的話收不回來（prompt 已要求不要先說）
- `qa-latency.jsonl` 不輪替、每次結束旅程整檔讀入（一趟的量很小）
- 每段都被語音管線當成「開場句」多試幾個 seed（段首同樣有專有名詞風險）
- 取消時 `to_thread` 裡已在跑的那一段無法中止，只是不再寫檔
- `reason` 用字串、`question/fix/more` 透傳：判斷題，未重構

**還沒做**：真實合成與端到端延遲量測（M3 上第一段要多久）——要實機／真實 Claude，須使用者先同意次數。

## #22 問答（主機）：問答優先使用 GPU，主動介紹讓路（2026-10-20，分支 `feat/v2-qa`）

做了：
- `SpeechPipeline.run(text, unit_guard=)`：每個合成單位（pipeline 的一個 chunk，含換 seed 重試）前後進出，排程用
- `speech/scheduler.py`（`SpeechScheduler`，取代 #21 的 `SerializedSpeech`）：介紹每個單位開始前，有問答排隊或進行中就等；正在合成的單位做完才讓路；問答全部做完介紹自動繼續。`narration` lane 給 `AreaPreparer`，`answers` lane 給 `QaService`
- **問答整個答案持有一張號碼牌**（`answers.begin()` → `turn.run(段)` … → `turn.end()`）：從開始回答到結束，包含等 Claude 寫下一段的空檔，介紹都不會插進來。`end()` 時還有一段在合成就等它做完才讓出 GPU；等待中被 `end()` 的 `run` 拋 `TurnEnded`；放棄／失敗／取消都會 `end()`
- `QaService` 以 `speech.begin()` 取得 turn，`finally` 一定 `end()`；額度擋下的問題不取號

驗證：host 560 項、ruff 乾淨；全程假合成器（刻意放慢＋Event 卡住）：問答先、介紹後；進行中的單位不被打斷；介紹最終完成；多個問答不同時合成；失敗的問答與介紹單位不卡住別人；Claude 寫字空檔介紹不插隊（含真的 `SpeechScheduler`＋`QaService` 的整合測試）；變異檢查（拿掉讓路條件測試會失敗）。**沒有呼叫真實 Claude／合成。**

code-review 後修正：
- 原本「每段答案各取一次號碼牌」：Claude 寫下一段的空檔介紹會插進來、下一段問答要再等一個介紹單位 → 改成整個答案持有
- `_Narration`／`_Answers` 不再存取 scheduler 私有屬性；補「介紹單位拋例外會釋放 busy」測試；`contextlib` import 移到檔頭

審查指出但刻意不改：
- 兩個介紹同時進來時，單位會交錯（原本的鎖是整段輪流）：實際上主機同一時間只跑一次準備（`TourSession`），不會發生
- 問答被取消後，`to_thread` 裡已在跑的那段仍合成到底才讓出 GPU（無法中止執行緒）
- `pending_answers` 目前只有測試與除錯用
- 獨立的 CLI（`narration`／`speech`／`phrases` 的 `__main__`）自己建 pipeline、不經排程器：手動工具，不在服務行程內

**還沒做**：真實 M3 上「介紹合成到一半時進來的問題要多等多久」的量測——要實機合成。

## #23 問答（App）：按住說話提問、播放答案（2026-10-20，分支 `feat/v2-qa`）

做了：
- `qa/qa_api.dart`（`HttpQaApi`：ask／answer 輪詢／逐段下載）；抽出 `host/host_http.dart`（送出、token、逾時、錯誤統一為 `TourApiException`）與旅程 API 共用
- `qa/speech_recognizer.dart`：引擎可注入；`QuestionListener` 先試本機 zh-TW、被拒絕（`OnDeviceUnavailable`）就改線上並記住；`SpeechToTextRecognizer`（speech_to_text）；Info.plist 加麥克風與語音辨識說明（有測試）
- `qa/qa_controller.dart`：按下開始聽、放開送出；念填空短句 1／2 交替；輪詢答案、出現一段就下載並播一段（各段之間不釋放 audio focus，整個答案播完才恢復）；8 秒沒有任何一段補短句 3、`searching_web` 補短句 4（各一次，已有語音就不補）；額度用完只在畫面提示不念；連不上主機沿用旅程的斷線處理；旅程結束取消
- `TourController`：`beginQuestion／endQuestion`（問答期間不開始新介紹、不念「連不上」）、`noteHostFailed／noteHostReached`、`position`
- `NarrationPlayer`：`releaseFocus`／`release()`；答案用另一個播放器與暫存檔
- UI：旅程中的「按住說話」（`Listener`，按下立刻開麥）、辨識方式、上網中、額度、錯誤提示；`FAKE_QUESTION` 假辨識
- 主機：重播模式（`--replay-dir`）開放問答，回固定假答案與提示音（`qa/replay.py`），供模擬器端到端

驗證：App 207 項、analyze 乾淨；host 566 項、ruff 乾淨。**模擬器端到端通過**（iPhone 16 模擬器：重播主機＋`FAKE_QUESTION`，出發 → 按住 → 放開 → ask → 輪詢 → 下載兩段 → 回到可再問；主機日誌確認）。全程沒有呼叫真實 Claude。

我的解讀（請使用者確認）：
- 「按下去立刻播短句」解讀成**放開（問完）之後**才播：按住時麥克風是開的，這時出聲會被辨識進去。若要按下就播，移動 `_submit` 的 `_say`，並要處理辨識與喇叭聲
- 「再多說一點」由 App 比對辨識出的文字（「再多說」「多說一點」…）決定是否帶 `more: true`

**還沒做**：
- #24：發問時正在播的介紹不會暫停、也不會從中斷的那句接著講（目前只是不再開始新的）
- 實機才驗得到：本機 zh-TW 辨識是否可用（#10）、放開後多久拿到最終文字、麥克風權限對話框、錄音與播放切換的 audio session（plugin 會暫時改成 playAndRecord 並在結束後還原，未實測）

遇到的坑：模擬器第一次建置時 `xcodebuild` 卡在 `ibtoold` 42 分鐘（只用了數秒 CPU）；終止後重跑 75 秒完成。

code-review 後修正（#23）：
- 取消後不釋放 audio focus（答案各段不釋放，只靠結尾的 release）→ `cancel()` 補 `release()`＋停短句
- 短句播完會釋放 focus，造成「短句 → 答案」之間音樂跳回來 → 短句也不釋放，整個答案播完一次恢復
- press → cancel → 立刻再 press 會讓舊的 `session.cancel()` 殺掉新錄音 → 以 `_starting` 串接，舊的收乾淨才開新的（有測試，含 listen／cancel 順序）
- `_audio` 鏈只攔 `Exception`，一個 `Error` 就讓之後的答案都靜音 → 改接住全部
- 短句其實排在 `session.finish()`（最久 3 秒）之後 → 放開當下就念，不等最終文字
- 問答對 HTTP 錯誤的斷線判斷與旅程輪詢不一致 → 對齊：只有 404 不算斷線，其他（含 401、5xx）算
- 驗證：App 212 項、analyze 乾淨；模擬器端到端重跑

審查指出但刻意不改：
- 本機 zh-TW 辨識判斷「不支援」靠套件的英文訊息字串、記住後整個 App 生命週期不重試、先成功過之後本機失敗不會降級線上：實機驗證本機辨識時（#10）再決定
- `SpeechToTextRecognizer` 沒有單元測試（只有實機驗得到）
- `QaController` 直接呼叫 `TourController` 的多個方法、`reason` 是字串、`(generation, id)` 成對傳遞：判斷題，未重構
- `FAKE_QUESTION` 的 override 留在正式 `main.dart`（用 dart-define 控制，預設不啟用）
- 模擬器端到端在修正後重跑通過（全新的 iPhone 16／iOS 18.6 模擬器）。原本那台模擬器跳出「Apple Account Verification」系統對話框（要輸入某個 Apple 帳號的密碼）擋住 App；這是帳號憑證，不由 agent 操作，改建一台沒登入帳號的模擬器繞開

## #24 問答：發問時暫停介紹，答完從中斷的那句接著講（2026-10-20，分支 `feat/v2-qa`）

做了：
- 主機：`speech/units.py`（`unit_starts(wav)`）從 wav 偵測各個合成單位的起點——管線在單位之間插入精確的靜音（全 0 樣本），所以快取命中的舊介紹、重播的介紹都有，不必改快取格式；`TourSession._publish` 把它放進通知事件的 `unit_starts`
- App：`NarrationInfo.unitStarts`（舊主機沒給＝空）；`resume_point.dart` 的 `resumePoint(position, unitStarts)`（落在某句前面 0.3 秒靜音裡視為句界）；`NarrationPlayer.play` 改回傳是否自然播完、可指定起點，並有 `position`
- `TourController`：`beginQuestion`（第一個）停下正在播的介紹、記住接續點；`endQuestion` 後（若使用者沒按暫停）從那一句開頭接著播，接續播完才回報「講過」；再被打斷會重新計算；結束旅程就丟掉；音檔還在下載時開始發問就先放回佇列

驗證：host 574 項、ruff 乾淨；App 231 項、analyze 乾淨（句中被打斷、剛好在句界、沒有介紹在播、暫停中、連續兩次打斷、結束旅程、下載中發問、舊主機沒有起點，都有測試）。全程 fake。

**沒有做 / 不確定**：
- 模擬器端到端沒有涵蓋「打斷介紹」：重播模式需要真實合成過的介紹 wav 才有句子，這邊沒有；實機（#8、#10）才驗得到實際聽感與 `position` 的準確度
- 被打斷時落在句子後面的靜音（上一句剛講完、下一句還沒開始，且超過 0.3 秒前）會重講上一句：主機只附起點、沒附終點；機率低且無害
- `unit_starts` 靠靜音偵測：單位內部若有超過 0.3 秒的「精確 0」靜音會多出一個起點（只會讓接續點更細，不會錯）

code-review 後修正（#24）：
- 競態（審查指出、有測試重現）：① 播放器在寫檔的空檔被 `stop()` 時打斷被吞掉，介紹照樣播完並與發問重疊；② 問題極短（答得很快）時，接續與舊播放的收尾交錯，`_busy` 被清掉、暫存檔被刪、介紹疊播或卡死；③ 已有接續點時再發問會用已停的播放器位置覆寫；④ 剛好在播完的同一刻發問，已回報的介紹末句會再播一次。
  → 播放器 `play()` 一開始就立好狀態；控制器每次播放有自己的 `_Playing`（旗標與完成訊號），接續要等舊的播放收尾完才開始，已播完的不打斷、已有接續點的不覆寫，等待收尾時又發問或暫停就把接續點留著
- 打斷時 `stop(releaseFocus: false)`：不讓其他 App 的音量在打斷與答案之間跳回來
- 句前靜音門檻 0.3 → 0.45 秒（管線預設的單位間隔）：減少在靜音尾段被打斷時重講上一個單位
- 主機 `unit_starts` 只認 16-bit 單聲道
- 驗證：App 234 項、analyze 乾淨；host 575 項、ruff 乾淨

審查指出但刻意不改：
- 起點粒度是「合成單位」（一個 chunk 可含多句）：issue 括號寫「各句（合成單位）」，已在 README 註明
- 單位內部若有超過 0.3 秒的「精確 0」靜音（模型輸出或 int16 截斷）會多出起點：只會讓接續點更細，不會錯；是靜音偵測的啟發式，不是管線記錄
- 主機端 `_publish` 同步讀 wav（120 秒實測約 15ms），未改成 `to_thread`
- `_silenceBeforeSentence` 與主機的 `MIN_GAP_SECONDS` 兩端各寫一份，靠註解同步

## #11 拍照提問（2026-10-20，分支 `feat/v2-qa`）

做了：
- 主機：`qa/photos.py`（`PhotoStore`：JPEG／PNG、8 MB、隨機檔名、權限 0600、保留 24 小時、存取與啟動時清理、不入 repo）；`POST /v1/qa/ask-photo`（base64＋位置＋指南針方向；400／413／503）；prompt 帶照片路徑、`Read` 工具與 `--add-dir`、指南針方向取代走路方向；`QaService.ask_photo` 與一般問答共用額度閘門、GPU 排程、用量記錄
- App：`qa/photo_source.dart`（`image_picker` 相機，縮圖、權限錯誤變成可顯示的訊息）、`qa/compass_source.dart`（`flutter_compass` 的 `headingForCameraMode`）、`HttpQaApi.askPhoto`（上傳逾時 30 秒、讀不到指南針就不帶方向）、`QaController.askWithPhoto`（與按住說話共用「送出 → 跟隨答案」）、「拍照問」按鈕、Info.plist 相機說明；`FAKE_PHOTO` 供模擬器
- 附帶修正：`JustAudioPhrasePlayer` 把短句排成一列、`stop()` 取消排隊中的，修掉剛念完「出發」就發問時的 Loading interrupted

驗證：host 600 項、ruff 乾淨；App 254 項、analyze 乾淨；**模擬器端到端通過**（全新模擬器＋重播主機＋`FAKE_PHOTO`：出發 → 拍照問 → ask-photo → 輪詢 → 下載兩段 → 回到可再問；主機日誌確認）。全程沒有呼叫真實 Claude。

**還沒做（須使用者同意才能做）**：
- 「Claude 能正確讀取照片並回答，回答經過自動驗收」的**真實驗證**：需要真的呼叫 Claude（每次約 50k～80k 輸入 token，Sonnet）。建議 1 次：用一張手機照片、問「這是什麼」，看 Claude 有沒有真的用 `Read` 讀到照片、答案是否合理、合成驗收是否通過。**先請使用者同意次數與哪一張照片**
- 實機：相機權限對話框、指南針準確度、錄音／拍照切換
- 風險（已寫進 host/README）：給了 `Read` 工具，Claude 技術上能讀主機上任何檔案；照片來自使用者自己的手機，屬已知取捨

code-review 後修正（#11）：
- **安全**：照片內容是第三方內容，可能夾帶指示。原本給了裸 `Read`＋`WebSearch`／`WebFetch`，理論上能被誘導讀 `claude-token` 再外送 → 拍照的問題不給上網工具、`Read` 限定在照片資料夾（`Read(//…/photos/**)`，語法經官方文件確認）、prompt 明說照片裡的字不是指示
- **安全（所有呼叫）**：預設內建工具集連 Bash 都有、唯讀指令免詢問 → `ClaudeCliClient` 每次呼叫加 `--tools`，只開這次需要的內建工具，沒有需要就全關（寫稿沒有上網需求的呼叫也因此不再帶一堆用不到的工具）。**尚未用真實 Claude 驗證這個旗標**
- Info.plist 與 README 原本寫「照片只傳給主機」不實 → 改成照實說：主機會請 Claude 看，影像會送到 Anthropic
- `PhotoStore`：資料夾 0700、清理不再因為列不出目錄而拋例外、寫到一半失敗不留殘檔；請求欄位上限對齊 8 MB
- 保留期限：原本只在存照片與啟動時清 → 每次發問清一次＋每小時背景清理
- `JustAudioPhrasePlayer`：載入音檔的空檔被 `stop()` 時不再繼續播
- 驗證：host 612 項、ruff 乾淨；App 254 項、analyze 乾淨

審查指出但刻意不改：
- 只在拍完照之後才讀指南針（使用者可能已轉動手機）：沒有「拍照當下」的鉤子可用，`image_picker` 不提供
- `_say` 與 `JustAudioPhrasePlayer` 各有一層排隊、「這是什麼？」在 App 與主機各寫一份預設：判斷題
- 照片存檔後若 `_start` 之前出錯不會回收：由保留期限兜底
- `--add-dir` 開整個照片資料夾（24 小時內的其他照片都讀得到）

## #8 iPhone 實機背景行為（2026-10-20，分支 `feat/v2-qa`）——**程式面完成，實機驗收未做**

已經有的（#7 就做了）：`UIBackgroundModes` 含 `location` 與 `audio`、Info.plist 的定位說明（有測試）、背景定位設定（`allowBackgroundLocationUpdates`、關掉自動暫停、背景定位指示）、耳機／鎖定畫面的暫停鍵與目前播放資訊（`audio_service`）。

這次做的：
- **請求「永遠」定位權限**：geolocator 在 Info.plist 有 WhenInUse 說明時只會要到「使用 App 期間」，不會升級。`tour/location_permission.dart`：先要「使用 App 期間」、拿到後請求升級成「永遠」（`permission_handler`，Podfile 開 `PERMISSION_LOCATION=1`，iOS 建置通過）；使用者可以只給前者，照樣能出發，升級詢問出錯也不影響已拿到的權限
- 只有「使用 App 期間」時，畫面有紅字提醒鎖定螢幕可能收不到位置（`TourState.locationAccess`）
- `docs/device-verification.md`：**實機驗收清單**（背景 15 分鐘、鎖定畫面、暫停鍵、duck、耗電、本機 zh-TW 辨識、問答延遲、拍照），附結果表格給使用者填

驗證：App 267 項、analyze 乾淨；`flutter build ios --simulator` 通過。

**未做（agent 做不到，必須實機）**：issue #8 的「實機鎖屏 15 分鐘以上位置回報與自動播放持續」「鎖定畫面顯示與暫停鍵有效」「記錄耗電觀察」。請使用者照 `docs/device-verification.md` 驗，把結果貼到 issue。不關 #8。

注意：請求「永遠」的 iOS 行為（升級詢問何時跳出、使用者選擇後的狀態）只有實機看得到。

刻意的決定（#8）：**不強制「永遠」**。issue 與設計文件只說「定位權限要 Always」，沒說拒絕就不能出發；iOS 也不能一次直接要 Always（必須先 whenInUse 再升級）。使用者只給「使用 App 期間」時照樣能出發（出發時 App 在前景、有背景定位指示，iOS 會讓更新持續），但畫面會提醒。**「使用期間」鎖屏是否真的會中斷、要不要改成強制，等實機驗證的結果再決定。**

code-review 後修正（#8）：
- 「永遠」升級詢問加逾時（20 秒）：iOS 沒跳詢問或使用者還在想時不卡住出發，先沿用目前權限
- `requestAlways` 可能在使用者回答之前就先回來（permission_handler 已知的時序問題），而且權限只在出發當下快照 → App 回到前景時重讀（`TourController.refreshLocationAccess`、`HomeScreen` 的 `WidgetsBindingObserver`），使用者到「設定」改成「永遠」後紅字會消失
- Podfile 巨集只加在 `permission_handler_apple`（原本所有 Pod 都加，69 處 → 3 處）
- 實機清單的對話框字樣改成 iOS 實際的「保留使用 App 期間」「改為永遠允許」，並加一項「改成永遠後紅字消失」
- 驗證：App 270 項、analyze 乾淨；`flutter build ios --simulator` 通過

審查指出但刻意不改：`TourState.locationAccess`（預設 always）與 `GeolocatorLocationSource.access`（預設 denied）的預設值不一致、且有「要先呼叫 ensurePermission」的時序耦合——紅字只在旅程進行中顯示，目前不會出錯；之後可讓 `ensurePermission` 直接回傳 `LocationAccess`

## 收尾對照（2026-10-20）

追蹤器上 `ready-for-agent` 的 open issue 剛好是這 8 張（#8、#10、#11、#20～#24），都已處理到 agent 能做的程度。**沒有關任何 issue、沒有 push**。

- #20～#24：完成，合併後可關
- #10（父單）：子單 #20～#24 完成；它的實機項目已拆成 **#25（ready-for-human）**，由使用者在實機上做，所以 #10 要等 #25 才能關
- #11：程式完成；「Claude 真的讀得到照片並答對」要真實呼叫 Claude（須使用者同意次數）
- #8：Always 權限請求與提示完成；鎖屏 15 分鐘、鎖定畫面暫停鍵、耗電要實機

另外：`implement` skill 設定為只能由使用者以 `/implement` 啟動（`disable-model-invocation`），agent 不能呼叫；這次是照它的內容手動執行（TDD → 型別檢查／單一測試檔 → 最後跑全套 → `/code-review` → commit）。

## PR #26 review 之後（2026-10-20）

PR 上的獨立整合審查（https://github.com/wm4n/ai-tour-guide/pull/26）發現並已修：
- **MUST**：旅程自己撞額度後，若問答先探測成功把閘門打開，介紹要等人走滿 250 公尺才會補準備（`_stop` 的 quota 分支漏清 `_anchor`；有測試重現）
- 非 ASCII 的 `X-Buddy-Token` 讓主機回 500（`compare_digest` 對非 ASCII 的 str 丟 TypeError）→ 改比位元組（header 以 latin-1 還原、token 以 UTF-8）；設定檔的 token 含中文也能用
- 問答把主機有回應的 4xx（400／401／413）當成「連不上主機」→ 只有沒回應與 5xx 才算斷線，4xx 只在畫面顯示且不重試
- 答案播放中碰一下按鈕又被系統取消，會停掉整個答案 → 只有「按住中」才因 pointerCancel 取消
- 主機重啟後 `out/answers/` 舊音檔永遠不清 → 啟動時 `clear_stored_audio()`
- 照片 base64 解碼與存檔改在執行緒裡，不卡事件迴圈

第二輪（2026-10-21，使用者要求把還沒處理的建議修完）：
- **取消端點** `POST /v1/qa/cancel?id=`：`QaService.cancel` 先標 `failed／cancelled`、取消任務；`_answer` 收尾拆成兩層 `finally`，收尾時又被取消也一定 `turn.end()`（否則 GPU 號碼牌洩漏、之後所有介紹卡住）。`ClaudeCliClient` 被取消時和逾時一樣殺掉 claude 行程（原本只殺逾時，取消會留下行程繼續耗額度）。App：旅程結束／`cancel()`、逾時、「送出時就已取消、主機回應才到」三條路都通知主機（送不到不報錯）
- 提早失敗時開場短句與被打斷的介紹疊在一起 → `_finish` 先等還在念的短句念完才恢復音量、讓介紹接著播（失敗訊息因此晚約一句短句的時間才出現）
- JSON 契約測試：`contract/` 放主機實際輸出的範例，主機測試比對、App 測試讀同一份

**還沒處理（需要真實呼叫）**：
- `--tools` 對所有呼叫生效、尚未用真實 Claude 驗證（見下方「真實 Claude 驗證」）
- 取消時 `to_thread` 裡已在跑的那一段合成仍會做完才讓出 GPU（無法中止執行緒）

驗證：host 623 項、ruff 乾淨；App 282 項、analyze 乾淨。

## #28 每個聲音可設定語速，回答問題可壓縮長停頓（2026-10-21，分支 `feat/voice-speed`，PR #29）

起因：等 M6 期間試新參考聲音，有的聲音聽起來像在慢慢唸稿（約 4.4 字／秒）。

- 試過被否決的：對成品做時間伸縮（librosa 相位聲碼器）——聲音怪；換語速比較快的參考段落——成品語速不變（4.5→6.1 字／秒的參考，成品都是 4.3～4.4）。
- 採用：在聲碼器之前把 mel 時間軸插值壓短（`install_speed`），1.2 倍試聽沒有怪聲；回答問題再把超過 0.45 秒的停頓縮短（`speech/pauses.py`）。使用者評：壓停頓的像聊天、沒壓的像說故事，所以介紹不壓、問答壓。
- 設定放在各聲音的 `voice.toml`（使用者要求：不是每個聲音都這樣，其他聲音照舊）；`config.toml` 的 `voice` 選聲音；介紹快取記聲音鍵，換聲音用舊稿重新合成、不再呼叫 Claude。
- 端對端（同一份 234 字稿、完整驗收）：介紹 56.0 秒、問答 48.9 秒，與試聽版本（55.6／48.8）一致；原速 66.5 秒。

**踩到的坑**：拿 `out/narrations` 的舊成品（34.7 秒）當 F2 的長度基準，推出「這個聲音慢一倍」「參考錄音的節奏會被學走」兩個錯誤結論；那份成品其實有兩句被跳過、而且是舊版管線。用今天的管線重跑 F2 是 75 秒。比較長度一定要同一條管線、同一份稿子當場重跑。

**還沒做**：使用者親耳驗收正式版（`~/.buddy-host/out/voice-final/`）；選定正式聲音；App 固定短句換聲音後要重做；字音（「廟」→「秒」等聲調錯誤，Whisper 驗收抓不到）。

驗證：host 661 項、ruff 乾淨。

## #33 設定頁：看到主機上的聲音並試聽（2026-10-29，分支 `feat/voice-settings-list`）

- 主機：`voice.toml` 接受 `display_name`、`description`；`GET /v1/voices`（只列有 `voice.toml` 的資料夾、含 `key`、`phrases_ready`、`current`，每次重讀硬碟，壞掉的 `voice.toml` 只略過那一個）；`GET /v1/voices/{name}/phrases/{number}`（只認清單上的聲音與 `PHRASES` 編號，不拿輸入拼路徑）。`current` 這張仍是 `config.toml` 的 `voice`，狀態檔是 #34。
- App：齒輪改開完整設定頁（聲音／家裡的主機）；聲音清單、反灰、目前聲音未準備或不在清單上的警示；離線時顯示最後一次看到的目前聲音（存在 SharedPreferences）。
- 試聽：從主機下載 7 號短句、用自己的播放器（`buddy_preview.wav`）播；沿用 `beginQuestion`／`endQuestion`，`endQuestion` 在 `finally`，下載失敗也一定放開，旅程不會卡住。連按別的聲音：先占住再停前一段，介紹不會在兩段試聽之間被接回去。發問中不能試聽。
- `contract/voices.json`：主機與 App 讀同一份回應。範例顯示名稱用「示範女聲／示範男聲」，真正的名稱只放主機的 `voice.toml`。
- `/code-review` 後修：`VoiceState` 補 `copyWith`；試聽失敗區分「短句沒準備（404）」與「連不上主機」；目前聲音不在清單上要警示。
- 沒照建議改的：設定頁測試留在 `home_screen_test.dart`（從齒輪進去的整合測試、共用同一組 provider）；`beginQuestion` 不改名（語意是「占住介紹」，試聽與發問共用）。

- PR #41 review 後修：試聽播放器丟出非網路錯誤（壞掉的 wav）時顯示「無法播放」，不再成為未處理的例外。

驗證：host 721 項、ruff 乾淨；App 314 項、analyze 乾淨。試聽的音質要等 #37 實機驗收時人耳聽。

## #34 從設定頁切換聲音（2026-10-29，分支 `feat/voice-switch`）

- 主機：`POST /v1/voice`（不存在 404；短句未準備、缺參考錄音或逐字稿 409；切到目前聲音 200 不做事）。立刻回應，合成器在下一個合成單位才換（#38 的 `change_voice`；回答整題用同一個聲音），切換時重讀 `voice.toml`。選擇存在 `voice/current`（原子寫入），`main()` 只解析一次、優先於 `config.toml`，記的聲音不見了就退回。啟動時目前聲音短句未準備會在日誌警告。
- 換聲音時介紹準備器的聲音鍵跟著換。**這一批開始後聲音換了**，剩下的只存稿不合成；合成到一半換了，就丟掉那段音檔（排程器在單位之間換聲音，那段可能混了兩個聲音），不發布也不寫入任何聲音的快取。稿子都留著，之後用新聲音重新合成，不再呼叫 Claude。#31 原本的測試斷言「合成到一半換了仍存在起始聲音底下」，那時聲音不會在執行中換，這次改成新的預期。
- App：點選聲音後，先把 6 句固定短句全部下載進記憶體，再一次存進手機的 `文件/phrases/<聲音鍵>/`（先寫 `.tmp` 再 rename）。接著 `POST /v1/voice`，成功才記住。任何一步失敗（含手機存不下）都不換，並提示原因。切換中，那一列顯示進度，仍可以再點別的聲音（包括點回原本的聲音來取消），以最後一次為準。**換聲音的請求照點選順序送**（用 tail future 串起來）；mutation 測試確認，拿掉串接後「依點選順序」的測試會紅。
- 固定短句優先念手機裡目前聲音的檔案，念的當下才 `ref.read`。不用 watch，否則試聽或切換時會重建播放器，把正在念的短句切掉。手機裡沒有就退回 App 內建的。
- 目前聲音以主機為準：開設定頁、或連線從斷到通（HomeScreen 的 `ref.listen`）時同步，手機裡沒有它的短句就自動下載，不送 POST。
- `/code-review` 後修：抽出 `find_voice`；`select()` 改用 `_currentOf`；存檔失敗要提示；切換中可以點回原本的聲音；prefs 常數改名；測試 helper 去重。
- 沒照建議改的：`voice_api.dart` 兩段雙 catch 維持（和 `tour_api.dart` 一致）；`warn_if_phrases_missing` 回傳 bool 留著給測試；`select()` 的世代計數加 tail future 留著（兩件事各有測試擋：放棄過期的下載、依序送請求）。
- 留給後續票：「這段播完就換，下一段準備中…」的提示，以及已準備好、未播的舊聲音介紹丟掉重做，屬於 #35；`played_ids` 與停住佇列屬於 #36。

驗證：host 742 項、ruff 乾淨；App 340 項、analyze 乾淨。
