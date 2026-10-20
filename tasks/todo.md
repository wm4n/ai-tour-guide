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
