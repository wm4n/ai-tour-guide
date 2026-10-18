# 使用者偏好

## 開發流程（2026-10-19）

- brainstorming 完成的項目 → 開 GitHub issue（父單）追蹤 → `/grill-me` 拷問到沒有問題、把結論補回 issue 與設計文件 → `/to-tickets` 拆開發子單並設定 GitHub 原生 dependency → `/implement` 依相依順序逐張開發。
- 不再使用 OpenSpec（`opsx:*`）；`openspec/` 只保留 v1 歷史。
- `grill-me`、`to-tickets`、`implement`、`setup-matt-pocock-skills` 設為只能由使用者以 `/指令` 啟動，agent 不能自行呼叫。

## 產品偏好（v2）

- 語音要有人味、像朋友聊天；機器音、念稿感是失敗。
- 旅行習慣是「走到哪看到哪」，不依賴事先排好的行程。
- 成本：LLM 只用 Claude Pro 訂閱，用完就停；其他服務必須在免費額度內並設硬上限。
- 想實測 Claude Pro 額度上限，不設每趟用量上限，但要記錄用量。

## Repo

- 本 repo 是公開的：不提交金鑰、主機位址、參考聲音檔與其逐字稿，也不在文件中寫出參考聲音來源人物的姓名。
