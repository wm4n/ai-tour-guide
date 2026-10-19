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
- 待辦：問答模式（放寬重試）先不做，使用者聽完再說；開車時是否縮短目標秒數：使用者說不用；稿子裡「全臺北最大的迎神祭典」「屋頂上有小人偶」等說法尚未用維基原文查證；App 要在哪裡選同行者留給 #7

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
