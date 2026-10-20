## Why

目前導覽播放仍綁在前景生命週期，使用者一旦把 App 切到背景或鎖屏，附近景點即使被偵測到也不會持續播放長篇導覽。這個改動要把產品行為補齊成真正可放口袋、戴耳機或車載使用的背景導覽模式，並先完成 Android 端可驗證的第一版。

## What Changes

- 新增旅程導覽播放佇列，讓新的 POI 觸發事件在目前旁白播放中不插播，而是依序排隊播放。
- 新增旅程播放模式設定，支援 `Auto-play` 與 `Notify only` 兩種背景觸發行為。
- 新增使用情境設定，支援 `Portable tour` 與 `Car tour`，並套用不同的排隊項目過期與距離規則。
- 調整觸發流程，讓啟動中的旅程在 Android 背景狀態下仍可提交候選 POI 到播放佇列或通知路徑，而不是被前景 lifecycle gate 擋下。
- 導入 Android 背景媒體播放邊界，提供鎖屏後持續播放、目前 POI 媒體資訊，以及基本播放/下一則控制。
- 更新旅程開始與結束流程，在需要時提示背景定位或通知權限，並在結束旅程時清空播放佇列與停止背景播放相關狀態。
- 在既有旁白 UI 補上最小必要的佇列資訊與「下一則」語意的跳過控制。

## Capabilities

### New Capabilities
- `tour-playback-queue`: 管理長篇 POI 旁白的排隊、去重、過期檢查、播放模式判斷、使用情境規則與旅程結束時的清理行為。
- `background-media-playback`: 提供 Android 背景媒體播放能力，包含媒體服務宣告、背景播放延續、目前 POI 媒體資訊，以及基本播放控制。

### Modified Capabilities
- `trigger-engine`: 將「觸發即立刻 narrate」改為「觸發即提交候選項」，並在旅程啟動後允許背景狀態持續驅動 auto-play 或 notify-only。
- `tour-session`: 更新開始旅程的權限檢查與引導，並要求結束旅程時同步清空播放佇列、停止旁白與關閉相關背景流程。
- `narration-stream`: 調整單一旁白播放責任邊界，讓 skip/stop 能與播放佇列協作，並在既有播放 UI 顯示最小必要的排隊資訊。

## Impact

- 受影響系統：Flutter 前端的 journey/session、trigger、narration、settings、notification、audio service 與 Android manifest 設定。
- 受影響平台：此 change 以 Android 背景播放與背景定位體驗為優先；iOS 不在本次範圍。
- 受影響依賴：需要在現有 `just_audio` 邊界上導入 `audio_service` 對應的媒體服務設定。
- 風險重點：背景定位前景服務與媒體播放前景服務需要共存，並避免造成重複或混亂的常駐通知體驗。
