## Context

目前 backend TTS 實作為 `GeminiTtsAdapter`，使用 `gemini-2.5-flash-preview-tts` 模型。合成流程為同步 API call（在 thread pool 中執行），輸出 PCM bytes，再以 `_pcm_to_wav()` 包裝成 WAV 格式，透過 SSE 分塊串流給 Flutter client。Flutter 的 `AudioPlayerService` 將每個 chunk 存為 `.wav` 暫存檔後以 `just_audio` 播放。

`TtsProvider` 是一個 Protocol（structural subtyping），只定義 `synthesize(text, voice_id, opts) -> AsyncIterator[bytes]` 介面，adapter 替換不影響任何呼叫端。

## Goals / Non-Goals

**Goals:**
- 以 `EdgeTtsAdapter` 取代 `GeminiTtsAdapter` 作為預設 TTS provider
- 更新 5 個 persona YAML 的 voice ID 至 Edge TTS 格式
- 更新 Flutter audio chunk 副檔名 `.wav` → `.mp3`（Edge TTS 輸出格式）
- 新增 `EdgeTtsAdapter` 單元測試

**Non-Goals:**
- 不修改 `TtsProvider` Protocol 介面
- 不修改 SSE 協議或 `/narration` API 合約
- 不引入動態 TTS provider 切換機制
- 不修改 `GeminiTtsAdapter`（保留但不 wire）

## Decisions

### Decision 1: EdgeTtsAdapter 使用 async generator，移除 PCM→WAV 轉換

**決策**：`EdgeTtsAdapter.synthesize()` 直接 `async for chunk in communicate.stream()` yield `chunk["data"]`（MP3 bytes），移除 `_pcm_to_wav()` 工具函數的使用。

**理由**：`edge-tts` 原生輸出 MP3，不需要格式轉換。`just_audio` 支援 MP3，且 MP3 codec 更廣泛。WAV 轉換邏輯是為 Gemini PCM 輸出設計的，對 Edge TTS 完全多餘。

**替代方案考量**：將 PCM→WAV 保留並讓 Edge TTS 輸出 WAV —— 否決，edge-tts 不支援原生 WAV 輸出，需要額外 audio 處理 library，增加複雜度。

### Decision 2: 保留 GeminiTtsAdapter，僅更換 wiring

**決策**：`tts.py` 保留 `GeminiTtsAdapter` class，僅在 `main.py` 將 wiring 從 `GeminiTtsAdapter` 改為 `EdgeTtsAdapter`。

**理由**：最小化 diff，保留回退選項。若 Edge TTS 出現問題，只需一行 code 即可還原。

### Decision 3: Voice ID 直接寫入 YAML，不設環境變數

**決策**：persona YAML 的 voice ID 欄位直接更新為 Edge TTS voice name（如 `zh-TW-YunJheNeural`），不透過環境變數動態注入。

**理由**：voice 是 persona 定義的一部分，屬於 prompt engineering 範疇，與 API key 等環境相關配置性質不同。Edge TTS voice 無需 API key，沒有多環境差異問題。

### Decision 4: Flutter 副檔名為 `.mp3`

**決策**：`AudioPlayerService` 的暫存檔由 `narration_$i.wav` 改為 `narration_$i.mp3`。`dispose()` 的清理邏輯同步更新。

**理由**：副檔名影響某些系統的 MIME type 偵測。`just_audio` 可依副檔名提示選擇正確 codec。

## Risks / Trade-offs

- **Edge TTS 網路依賴**：Edge TTS 呼叫微軟伺服器（非本地），開發環境需要網路。若微軟 API 不可用，TTS 整個失效。→ Mitigation：維持 `GeminiTtsAdapter` 保留在 codebase，緊急回退只需改一行。

- **MP3 音質與延遲**：Edge TTS 串流 MP3 chunk 大小和延遲與 Gemini PCM 不同，可能影響首個 chunk 到達時間。→ Mitigation：Edge TTS 採用 streaming 模式，首個 audio chunk 通常在 <1s 內到達，實測驗證。

- **TTS opts 未完全映射**：`TtsOpts.speaking_rate` 和 `emotion` 在 Edge TTS 中沒有直接對應（Edge TTS 以 SSML `rate` 和 `style` 控制）。初版 MVP 忽略這些 opts，直接使用 voice_id。→ Mitigation：MVP 可接受，後續可在 `EdgeTtsAdapter` 中加入 SSML 包裝。

## Migration Plan

1. 新增 `edge-tts` dependency 並 lock（`uv lock` 或 `pip install`）
2. 實作 `EdgeTtsAdapter`，本機測試串流輸出
3. 更新 persona YAMLs voice 欄位
4. 更新 Flutter `.wav` → `.mp3`
5. 更新 `main.py` wiring
6. 執行單元測試確認 mock stream 正確

**Rollback**：將 `main.py` 中 `EdgeTtsAdapter` 改回 `GeminiTtsAdapter`，還原 YAML voice IDs，還原 Flutter `.mp3` → `.wav`。

## Open Questions

- Edge TTS 在 Cloud Run 環境中的網路出口是否受限？需部署後驗證。
- `speaking_rate` / `emotion` opts 映射優先級：MVP 忽略，Phase 2 考慮 SSML 包裝。
