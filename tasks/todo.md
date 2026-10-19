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
分支 `feat/v2-buddy-tour`；**16 個本機 commit 尚未 push**（見「待辦」）。

### 狀態
| 票 | 狀態 | 備註 |
|---|---|---|
| #2 專案骨架 | 已關閉 | 實機（Tailscale）尚未驗證，留給 #15 |
| #3 Claude Code 介接層 | 已關閉 | 冷啟動約 3 秒、可讀圖、可呼叫本機 MCP；`utilization` 在 `unifiedWindows` 底下；每次新對話約 25k 輸入 token |
| #4 語音管線 | 已關閉 | 名花之里原稿 159 秒、10 段全過、RTF 4.44 |
| #16 語助詞 | 已關閉 | CER 量不出粵語腔；啊／喔／吧／一下下仍避免，待人耳確認 |
| #5 固定短句 | 開啟，接近完成 | 6 句（5、8 已取消）挑好並裁好；App 播放機制完成；只差關閉前的收尾 |
| #6 景點準備 | 開啟，接近完成 | 真實執行完成；發現的問題已修，等開場句驗證結果 |

### 使用者已同意／已決定（不要重問）
- Haiku 4 次（#3 探測）：已用完。Sonnet 2 次（#6 真實執行）：已用完；之後任何 Claude 呼叫都要重新取得同意
- 開場句驗收不過：選 **A**（多試 seed，不呼叫 Claude）
- 固定短句 5（額度用完）改成畫面提示、8（恢復）改成自動繼續，**都不念**；剩 6 句
- 挑選：1→seed42、2→seed42、3→seed99、4→seed42、6→seed2026、7→seed1234；成品在 `~/.buddy-host/out/phrases-final/`，**不入 repo**（公眾人物聲音的複製），用 `scripts/install-phrases.sh` 複製進 `app/assets/phrases/`（被 git 忽略）
- 用語：做兩岸用語詞表並由程式檢查（`host/config/taiwan_terms.json`）；固定短句的用語建議已貼在 #5，使用者回覆「不用念」所以不再改字
- Push：**先掃描機密再 push**（掃描方式：整段 `git log -p 86636e9..HEAD -- . ':!legacy'` 找 token／IP／ts.net／/Users/，再用真實 token 與參考逐字稿反向比對整個歷史，只輸出計數）

### 待辦
1. 開場句驗證：背景工作 `scratchpad/opening.log`（用真實引擎重跑兩份稿子的第一段，看開場句與廟名是否保住）。結果在 `~/.buddy-host/out/opening-check/`。機器 swap 幾乎滿，所以很慢
2. 驗證 OK → 關閉 #5 與 #6（#6 的記憶體結論：基準已用 13 GB、swap 峰值 23 GB，不是乾淨量測；乾淨環境與 M6 要重量），各留言附證據
3. 掃描機密後 push `feat/v2-buddy-tour`；更新各票留言裡過期的「尚未 push」
4. 使用者要聽 `~/.buddy-host/out/narrations-fixed/`（現有兩份音檔在接縫套了新裁切）確認接縫雜音是否消失；以及 `~/.buddy-host/out/particles-listen/` 確認啊／喔／吧／一下下的口音

### 踩到的坑
- **逐句合成會誤判**：兩個字的「哇！」四個 seed 的 CER 都 ≥ 1；管線改成先併段（約 90 字），整段失敗才往下拆（段 → 句 → 分句）
- **SSL**：python.org 版 Python 的 urllib 不認這台機器的憑證，用 `truststore`
- **MPS 的記憶體數字不可信**：`ps` 的 RSS、`/usr/bin/time -l` 都失真，改量系統層（vm_stat + swap）
- **公共 Overpass 常過載**：多鏡像站換站，整個失敗就降級為只用維基座標搜尋
- **真實資料才暴露的排序問題**：行政區標籤、街邊設施（YouBike）、同名重複，已排除
- **個性檔的範本比規則更有力**：範本若示範「哇！」Claude 就會照做；有測試守住
- **驗收的盲點（使用者試聽才發現）**：Whisper 常把句首語助詞與前導聲音當雜音省略，CER 照樣是 0。每個合成單位開頭有一小段 -25～-33 dB 的聲音，接著近乎靜音，約 0.45 秒才開口；Whisper 時間戳記抓不到，改用能量判斷開口點（`speech/onset.py`）
- **「額度」TTS 念不出來**：被念成「眾珠／過煮／夠度」，CER 0.083～0.167 仍過 0.2 門檻，所以短句（≤20 字）門檻收緊到 0.05
- **稿子開頭被整句跳過**：城隍廟前兩句（含廟名）、李臨秋故居第一句連換 4 個 seed 都驗收不過被丟掉，音檔沒念到名字；改成開場句多試 6 個 seed
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
