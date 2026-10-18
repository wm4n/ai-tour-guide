# KittenTTS 2 試聽 spike（2026-10-17～18）

一次性的 TTS 試聽比較，用來選定 AI Buddy Tour v2 的語音方案。結論已寫入
`docs/superpowers/specs/2026-10-18-ai-buddy-tour-v2-design.md`。

**不含任何音檔**：參考錄音取自公開 Podcast（公眾人物的聲音），僅供本人測試，不得進 git。

## 硬體與環境

- Apple M3、16 GB RAM，macOS；KittenTTS 2 跑 PyTorch MPS
- `kittenml==0.9.4`、Python 3.11（uv venv）、torch 2.14.1；`weights="packed"`、`decoder="default"`
- 自動驗收：openai-whisper `small`（CPU）+ OpenCC t2s 正規化後算 CER

## 比較過的方案（使用者主觀評價）

| 方案 | 評價 |
|---|---|
| Edge TTS（zh-TW 曉臻／雲哲） | 發音標準，但最像機器、像念稿 |
| KittenTTS 2 內建 `voice="Chinese"` | 中國腔太重，淘汰 |
| KittenTTS 2 + Edge 錄音當參考 | 較自然，但有怪音、夾英文怪 |
| BreezyVoice（MediaTek，CPU） | 發音標準，人味介於上兩者；M3 上 RTF 10～30，太慢 |
| KittenTTS 2 + 真人男聲參考（公開 Podcast 片段） | 書面稿很好；口語稿與短句會跑成類粵語腔 |
| **KittenTTS 2 + 真人女聲參考（F2）+ 自動驗收** | **採用**。短句穩定、名花之里長稿 checked 版「表現不錯」 |

## 關鍵發現

1. **參考錄音決定人味**：用機器聲當參考，學到的也是機器節奏；真人聊天錄音才有人味。
2. **口語語助詞會觸發粵語腔**：「欸、啊、喔、吧、一下下」等讓模型判斷成粵語；轉簡體無效（問題不在繁體字）。
3. **結果與 seed 有關**：同一句換 seed，有時正常、有時聽不懂；短句線索少最容易受影響。
4. **`normalize=False` 必須**：數字要先轉中文；日文假名要拿掉（保留羅馬拼音）；長串日期最容易失敗（4 次全敗，其中 2 次跑出 40 秒亂碼）。
5. **自動驗收有效**：CER ≥ 0.5 的壞版本都被攔下，多數重試 1～2 次過關（名花之里 13 句中 7 句重試）。
6. **驗收器的已知缺陷**：Whisper 輸出阿拉伯數字（2027），原稿是中文數字（二零二七），CER 被誤判偏高。比對前須統一數字寫法。
7. **句子切分**：KittenTTS 2 內建切句只認 ASCII `.!?`，中文需自行依「。！？」切句。

## 量測數字（M3，第三輪 F2 參考）

| 項目 | 數值 |
|---|---|
| 模型載入 | 12～22 s |
| 單句合成 RTF（首次嘗試） | 約 3～4（後段因記憶體壓力升到 6～9） |
| 名花之里：成品 150 s 音訊 | 合成總計 1457 s + 驗收 241 s（含重試，約 11 倍） |
| Whisper small 驗收每句 | 3～14 s |
| 峰值記憶體（KittenTTS 2 + Whisper 同 process） | 11.8 GB |
| 磁碟 | KittenTTS 2 權重約 1.9 GB（含 chatterbox-turbo s3gen 約 1 GB） |

## 檔案

- `run_kitten2.py`：第一輪 runner（內建聲音／聲音複製）
- `run_r3_autocheck.py`：第三輪 runner（切句 + seed 重試 + Whisper CER 驗收）
- `texts/`：測試稿（`35_nabana.txt` 是前處理後的版本；`12_spoken_with_particles.txt` 是會觸發粵語腔的口語稿）
- `autocheck_log.json`：第三輪每句每次嘗試的 seed、CER、Whisper 轉寫、耗時
- 參考錄音與逐字稿：不入庫，存放於主機本機 `~/.buddy-host/voice/F2/`
