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

範圍：不需要人類介入就能完成的 `ready-for-agent` 票（#2 → #3、#4 → #6、#16），#5 只產生候選。

| 票 | 狀態 | 備註 |
|---|---|---|
| #2 專案骨架 | 已關閉 | v1 移到 `legacy/`；Buddy Host（FastAPI）與 iPhone App 在 iOS 模擬器驗證「主機已連線／未連線」；實機（Tailscale）尚未驗證，留給 #15 |
| #4 語音管線 | 已關閉 | 名花之里原稿 159.3 秒、10 段全過、RTF 4.44 |
| #16 語助詞安全清單 | 已關閉 | 12 詞 × 3 句 × 3 seed；CER 量不出粵語腔，所以「啊」不改判安全 |
| #3 Claude Code 介接層 | 程式完成，**等 OAuth token** | 實測（冷啟動、讀圖、本機 MCP）已備好腳本、已取得 4 次 Haiku 的同意 |
| #6 景點準備 | 程式完成，**等 #3 與 2 次 Sonnet 的同意** | 免費 API 那一半已對真實 Overpass／維基百科驗證；記憶體峰值量測待真實執行 |
| #5 固定短句 | 候選已產生，**等使用者挑選** | 8 句各 3 個候選在 `~/.buddy-host/out/phrases/` |

驗證：`cd host && uv run pytest`（256 項）、`uv run ruff check .`；`cd app && flutter analyze && flutter test`（22 項）。

### 踩到的坑
- **逐句合成會誤判**：兩個字的「哇！」四個 seed 的 CER 都 ≥ 1（Whisper 對超短音訊會亂寫）。spike 其實是併成約 90 字一段，管線改成先併段，整段失敗才往下拆。
- **SSL**：python.org 版 Python 的 urllib 不認這台機器的憑證，Whisper 權重下載失敗；用 `truststore` 走系統信任庫。
- **MPS 的記憶體數字不可信**：`ps` 的 RSS 只有數十 MB、`/usr/bin/time -l` 的 footprint 也失真，所以另外做了系統層（vm_stat + swap）的取樣器。
- **公共 Overpass 常常過載**（官方站回 502 "at capacity"，連極簡查詢都失敗）：加了鏡像站換站，並在 Overpass 整個失敗時降級為只用維基座標搜尋。
- **真實資料才暴露的排序問題**：行政區標籤節點（「延平」）與以故居命名的 YouBike 站（帶品牌 wikidata）被當成景點，同一個地方的 way 與 node 佔兩個名額；mock 測不到。
- **個性檔的範本比規則更有力**：範本若示範「哇！」，Claude 就會照做；現在有測試檢查範本不含任何被禁用的語助詞。
- 模擬器上有 Apple ID 驗證的系統對話框會蓋住 App；改建一台乾淨的模擬器驗證，驗完刪除。

### 下一步（需要使用者）
1. 在自己的終端機執行 `claude setup-token`，把結果寫到 `~/.buddy-host/claude-token` 並 `chmod 600`（**不要**在 Claude Code 對話裡用 `!` 執行，token 會印進對話）
2. 之後執行 #3 的探測：`cd host && uv run python -m buddy_host.probe.run_probe --confirm-calls 4`
3. 同意 #6 的真實執行（2 次 Sonnet）：`uv run python -m buddy_host.narration --lat 25.0553 --lon 121.5098 --heading 0 --confirm-llm-calls 2`
4. 試聽並挑選 #5 的固定短句；試聽 `~/.buddy-host/out/particles-listen/` 確認啊／喔／吧／一下下的口音
5. 決定是否 push `feat/v2-buddy-tour`（已關閉的 issue 指向目前只存在本機的 commit）
