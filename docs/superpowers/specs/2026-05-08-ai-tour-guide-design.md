# AI Tour Guide — 設計文件

| 欄位 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 撰寫日期 | 2026-05-08 |
| 適用範圍 | v1（自用、無登入、全球通用式 AI tour guide） |
| 後續文件 | Implementation plan（待建立） |

## 實作進度（2026-05-13 更新）

| Plan | 內容 | 狀態 |
|---|---|---|
| **A** | Backend MVP — FastAPI + LiteLLM + Gemini TTS/LLM | ✅ 完成 |
| **B** | Flutter App MVP — 地圖、POI marker、旁白播放 | ✅ 完成 |
| **C** | Persona 系統（5 個）+ 雙語旁白（zh-TW / en） | ✅ 完成 |
| **D** | Push-to-talk Q&A（`/qa` SSE endpoint） | ✅ 完成 |
| **E** | 食家 persona + Google Places | 未開始 |
| **F** | 背景定位 + 部署上線 | 未開始 |

Plan C 實作細節見：`docs/superpowers/specs/2026-05-12-plan-c-persona-i18n-design.md`
Plan D 實作細節見：`docs/superpowers/specs/2026-05-13-plan-d-push-to-talk-design.md`

---

## 1. Overview

可帶出門的 AI tour guide 行動 App。使用者啟動「旅程」後，App 在前景與背景持續偵測位置；當進入符合條件的景點半徑時，自動由使用者選定的 persona（角色）以該角色獨特的口吻、語速、音色，串流式生成並播放景點介紹旁白；使用者可隨時 push-to-talk 提問，AI 以同 persona 即時回答。

### 1.1 核心使用情境

- 使用者按「開始旅程」→ 選擇 persona（例：歷史大叔）+ 語言（例：繁體中文）
- App 持續偵測位置（前景 + 背景）
- 走進故宮博物院 100m 範圍 → 自動觸發旁白「歷史大叔」風格的故宮介紹
- 使用者按住「我想問」按鈕：「這個館為什麼這麼重要？」→ 鬆開 → AI 以同 persona 回答
- 走出 POI 範圍但旁白繼續播完
- 接下來如果 100m 內又有別的景點，排隊依序播
- 按「結束旅程」→ session 結束

### 1.2 設計原則

1. **Provider Abstraction 是一等公民**：LLM / TTS / STT 各自有 interface，換 provider 是換 adapter，不是改架構
2. **串流是預設**：旁白是 LLM streaming → 句子切分 → TTS 逐句合成 → 音訊隊列 → 連續播放，首字延遲 ~2 秒
3. **裝置端是「狀態機」、後端是「無狀態管線」**：cooldown、history、設定都在裝置端 SQLite；後端只負責「給座標出旁白、給音訊出問答」，重啟不影響使用者
4. **Persona-coloured everything**：UI 文案、錯誤訊息、低資料 hedge 都由當前 persona 用自己的口吻講
5. **幻覺當特色**：低 confidence 時不抑制 LLM 創作，反而以 persona 化標籤（「🎲 大哥哥純粹在唬爛了，當聽故事就好 XD」）讓使用者知道這是表演成分

---

## 2. 關鍵決策摘要

| 決策項 | 選擇 | 理由摘要 |
|---|---|---|
| POI 資料策略 | 通用式 + 全球 | 不限策展景點，走到哪聽到哪 |
| 觸發模型 | 半自動 session（按開始旅程啟動） | 使用者掌控感 + 電量可控 + 避免誤觸 |
| 互動模式 | 旁白為主 + push-to-talk 提問 | 以單向旁白沉浸為核心，問答是加分功能 |
| 音訊核心 | TTS 串流播放 | 「會講話」是賣點，非 nice-to-have |
| 後端託管 | Google Cloud Run（A1） | scale-to-zero、自用 ~$0、60 分鐘 streaming timeout |
| 後端語言 | Python + FastAPI | LiteLLM、Google GenAI SDK 原生支援 |
| LLM 抽象層 | LiteLLM（選項 2） | OpenAI 相容 proxy，換 provider 改字串、不抹平 prompt caching |
| AI 服務組合（v1） | 全 Gemini free tier | LLM / TTS / STT 一家全包，自用 $0；隱私代價：input/output 用於訓練（自用可接受） |
| Google Places | v1 引入（食家 persona 專用） | 食家若無評分數據基本廢掉；$200/月免費額度自用吃不完 |
| 登入 | v1 無登入（自用） | 簡化所有架構 |
| UI / 旁白語言 | 繁體中文 + 英文 | 雙語對等支援 |
| Persona 數量 | 5 個 | 故事大哥哥 / 歷史大叔 / 八卦阿姨 / 童趣小妹 / 美食家 |
| Persona 切換時機 | 每次開新 session 時選 | 「換角色看世界」的體驗賣點 |
| Persona voice | Gemini 內建音色 mapping | v1 不糾結，v2 可升 ElevenLabs |
| POI 資料來源 | OSM (Overpass) + Wikipedia 混合 | 完全免費；Wikipedia 條目敘事豐富 |
| 食家專屬資料來源 | Google Places (Nearby + Details) | 評分、評論、招牌 |
| 旁白快取 key | (POI, persona, lang, length) | 「再講一次別的」可 force regenerate |
| 觸發半徑 | 預設 100m，使用者可調 30-300m | UI slider，即時生效 |
| 查詢半徑（內部） | 固定 500m | 確保接近時 POI 已在隊列 |
| 過濾條件 | 一般 persona：tourism/historic whitelist + 必有 wiki tag；食家：rating ≥ 4.3 + 50 評論，用餐時段加權 | 過濾掉 7-11、加油站；食家評分門檻避免雷店 |
| Cooldown | 預設 24h，可調 1h/6h/24h/3d/永不重複；以 POI 為 key（換 persona/lang 不重置） | 避免通勤路線轟炸；換版本不算新「景點」 |
| 多 POI 處理 | 排隊依序播（C2） | UI 顯示「下一站：X」 |
| 走出範圍 | 繼續播完（D1） | 旁白完整體驗優先 |
| TTS 串流模式 | LLM 串流 → 句子切分 → TTS 逐句 → 音訊隊列 | 首字延遲 ~2 秒，是體驗成敗關鍵 |
| 提問模式 | Push-to-talk（F1） | 收音邊界明確，避免 VAD 複雜度 |
| 背景定位 | A2 前景+背景持續（session 期間） | 「貼身導遊」必要條件 |
| 裝置 DB | drift / SQLite | type-safe、查詢能力強 |
| 旁白長度 | 預設 1-3 分鐘 / 3 段（簡介→故事→趣聞），可調 short/medium/long | 平衡資訊密度與耐心 |

---

## 3. 系統架構

### 3.1 高層架構圖

```text
┌────────────────────────── Flutter App (iOS / Android) ──────────────────────────┐
│                                                                                  │
│   ┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│   │ Session     │   │ Location     │   │ Trigger      │   │ Audio Player    │  │
│   │ Controller  │←─→│ Service      │──→│ Engine       │──→│ (FIFO queue)    │  │
│   │ (start/stop)│   │ (前景+背景)   │   │ (geofence/   │   │ + 串流播放       │  │
│   └─────────────┘   └──────────────┘   │  cooldown/   │   └─────────────────┘  │
│         ↓                              │  dedup)      │           ↑            │
│   ┌─────────────┐   ┌──────────────┐   └──────────────┘           │            │
│   │ Persona     │   │ Local DB     │           ↓                  │            │
│   │ Picker      │   │ (drift/      │   ┌──────────────────────────┴────────┐  │
│   └─────────────┘   │  SQLite)     │   │ Backend Client (HTTPS / SSE)       │  │
│                     └──────────────┘   └──────────────────────────┬────────┘  │
│                                                                    │            │
│                                                ┌───────────────────┴────────┐  │
│                                                │ Mic Recorder (push-to-talk) │  │
│                                                └────────────────────────────┘  │
└──────────────────────────────────────────────────┬───────────────────────────────┘
                                                   │ HTTPS / SSE streaming
                                                   ▼
┌──────────────── Cloud Run Backend (Python / FastAPI) ───────────────────────────┐
│                                                                                  │
│   API Layer:  /poi/nearby   /narration (SSE)   /qa (SSE)   /health              │
│                       │              │                │                          │
│                       ▼              ▼                ▼                          │
│   ┌────────────────┐   ┌──────────────────────────────────────────────────────┐ │
│   │ POIService     │   │ NarrationService / QAService                         │ │
│   │ ├─ Overpass    │   │  ┌──────────┐  ┌─────────┐  ┌───────────┐  ┌──────┐ │ │
│   │ ├─ Wikipedia   │──→│  │ Persona  │→ │ LLM     │→ │ Sentence  │→ │ TTS  │ │ │
│   │ └─ GooglePlaces│   │  │ Builder  │  │ (Gemini │  │ Splitter  │  │      │ │ │
│   └────────┬───────┘   │  └──────────┘  │ via     │  └───────────┘  └──────┘ │ │
│            │           │                │ LiteLLM)│                          │ │
│   ┌────────┴───────┐   │                └─────────┘                          │ │
│   │ POI Cache      │   │  + NarrationCache  + STT (Gemini multimodal)        │ │
│   │ (filesystem)   │   └──────────────────────────────────────────────────────┘ │
│   └────────────────┘                                                            │
│                                                                                  │
│   ┌─── Provider Abstraction ────────────────────────────────────────────────┐  │
│   │  LlmProvider (LiteLLM)  │  TtsProvider (Gemini TTS)  │ SttProvider (Gemini)│ │
│   │  PoiSourceProvider (Overpass+Wiki | GooglePlaces, persona-aware routing)│  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 部署拓樸

- Backend：單一 Cloud Run 服務，Dockerfile 化部署，scale-to-zero
- POI 快取與 NarrationCache 落在容器 `/tmp/`（重啟會清，acceptable for v1；v2 可升 GCS bucket）
- App：iOS / Android 雙平台，從同一份 Flutter 程式碼出
- 後端僅一個 endpoint URL + `X-API-Key` 保護（避免 URL 外流被陌生人刷配額）

---

## 4. 模組劃分

### 4.1 Flutter App 模組

| 模組 | 做什麼 | 對外介面（精簡示意） | 依賴 |
|---|---|---|---|
| **SessionController** | 管理「旅程開始 / 結束」狀態 + persona / 語言選擇 | `start(persona, lang)` `stop()` `currentSession$` | LocationService, LocalDB |
| **LocationService** | 抽象 iOS/Android 定位 API（前景+背景），輸出座標串流 | `positionStream$` `requestPermission()` | platform plugins (geolocator) |
| **TriggerEngine** | 收座標串流 → 查附近 POI → 過濾 → 排隊 → 發出觸發事件 | `triggerStream$` `skip()` `replay(poi)` | BackendClient, LocalDB（cooldown） |
| **NarrationOrchestrator** | 收觸發事件 → 呼叫後端取旁白串流 → 餵給 AudioPlayer | `play(poi)` `stop()` `state$` | BackendClient, AudioPlayer |
| **AudioPlayer** | FIFO 音訊隊列 + 連續播放 + 暫停 / 跳過 + ducking | `enqueue(audioChunk)` `pause()` `skip()` `duck() / unduck()` | platform plugins (just_audio) |
| **MicRecorder** | Push-to-talk 錄音 → 送後端問答 | `startRecording()` `stopAndSend()` | platform plugins (record) |
| **PersonaPicker** | 開旅程時選 persona 的 UI + 持久化偏好 | `pick()` `defaultPersona$` | LocalDB |
| **LocalDB** | drift/SQLite 包裝，所有 query 都走這層 | `cooldown.has(poiId)` `history.add(...)` `settings.get/set` | drift |
| **BackendClient** | HTTPS / SSE 串流 client，包裝後端 API | `nearby(coord)` `narration(poi, persona, lang) → Stream` `qa(audio, ctx) → Stream` | dio / http |

### 4.2 Backend 模組

| 模組 | 做什麼 | 對外介面 | 依賴 |
|---|---|---|---|
| **API Layer (FastAPI)** | HTTP / SSE endpoint：`/poi/nearby` `/narration` `/qa` `/health` | OpenAPI spec | NarrationService, QAService, POIService |
| **POIService** | 給座標 + persona → 回 POI 列表（含背景資料） | `nearby(lat, lon, radius, persona) → List[POI]` `details(poi_id) → POIContext` | OverpassClient, WikipediaClient, GooglePlacesClient, POICache |
| **OverpassClient** | 包裝 Overpass API 查詢 + retry + 限流 | `query(bbox, tags) → List[OsmNode]` | requests |
| **WikipediaClient** | 給 wikidata/title → 回 Wikipedia summary + intro | `summary(title, lang) → WikiArticle` | requests |
| **GooglePlacesClient** | 包裝 Google Places API（Nearby + Details） | `nearby_restaurants(lat, lon, radius) → List[Place]` | requests |
| **POICache** | 區域 + POI 兩層快取，TTL 30 天 | `get(key)` `put(key, val, ttl)` | filesystem |
| **NarrationService** | 給 POIContext + persona + lang → 串流 LLM → 串流 TTS | `narrate(poi, persona, lang) → AsyncIterator[Event]` | LlmProvider, TtsProvider, SentenceSplitter, NarrationCache, ConfidenceClassifier |
| **QAService** | 給 audio + 當前 POI context → 答覆（串流文字+音訊） | `answer(audio, ctx) → AsyncIterator[Event]` | SttProvider, LlmProvider, TtsProvider |
| **SentenceSplitter** | 串流文字流 → 句子流（中英文標點兼容） | `split(textStream) → AsyncIterator[Sentence]` | 純函式 |
| **NarrationCache** | (POI ID, persona, lang, length) → 完整音訊 | `get / put` + invalidate via force_regenerate | filesystem |
| **PromptBuilder** | 組裝 persona system prompt + POI context + 旁白要求 | `build(persona, poi, lang, length) → Messages` | persona prompt 資源檔 |
| **ConfidenceClassifier** | 依 POI 資料豐度判定 high/medium/low | `classify(poi_context) → Confidence` | 純函式 |
| **LlmProvider (LiteLLM)** | LLM 抽象 | `chat_stream(messages, opts) → AsyncIterator[TextChunk]` | litellm |
| **TtsProvider (Gemini)** | TTS 抽象 | `synthesize(text, voice_id, opts) → AsyncIterator[AudioChunk]` | google-genai SDK |
| **SttProvider (Gemini)** | STT 抽象（Gemini 多模態） | `transcribe(audio_bytes, lang) → str` | google-genai SDK |

### 4.3 模組設計原則收斂

- Provider 三層完全獨立：將來換 Claude / ElevenLabs / Whisper 只是換 adapter
- `PromptBuilder` 是獨立模組：persona prompt 資源檔（YAML）跟程式碼解耦，調 prompt 不用改 service code
- `SentenceSplitter` / `ConfidenceClassifier` 是純函式：最容易單測、不依賴任何 IO
- 快取分兩層：POICache（POI 背景資料）+ NarrationCache（合成後音訊）— 各自 invalidate 條件不同
- 後端無狀態：所有 cache 都是「可被清掉、清掉只是變慢」，無 user state；重啟 / 多實例 / scale-to-zero 都無痛

---

## 5. 核心資料流

### 5.1 Flow 1：開始旅程 → 第一次觸發

```text
使用者                Flutter App                          Cloud Run
  │                      │                                    │
  │ 按「開始旅程」        │                                    │
  ├─────────────────────→│ PersonaPicker.pick()               │
  │ 選「歷史大叔」+中文    │                                    │
  ├─────────────────────→│ SessionController.start()          │
  │                      │   ├─ requestLocationPermission()   │
  │                      │   ├─ LocationService.start()       │
  │                      │   │   (前景+背景模式啟動)           │
  │                      │   └─ TriggerEngine.attach()        │
  │                      │                                    │
  │                      │ ←── 座標 (lat, lon) 每 5-10 秒     │
  │                      │                                    │
  │                      │ 距上次查詢移動 > 重查閾值          │
  │                      │   (內部常數，預設 250m)            │
  │                      │   是 → BackendClient.nearby(coord) │
  │                      │                                    ├─→ POIService.nearby()
  │                      │                                    │     ├─ persona 路由：
  │                      │                                    │     │   一般 → Overpass+Wiki
  │                      │                                    │     │   食家 → Google Places
  │                      │                                    │     └─ 過濾 + 排序
  │                      │ ←── List[POI]                      │
  │                      │ TriggerEngine.evaluate()           │
  │                      │   ├─ POI 在觸發半徑內？             │
  │                      │   ├─ cooldown 內？(LocalDB)        │
  │                      │   ├─ 同 session 已播？             │
  │                      │   └─ 通過 → 排入觸發隊列            │
  │                      │                                    │
  │                      │ NarrationOrchestrator.play(POI)    │
  │                      │     (進入 Flow 2)                  │
```

### 5.2 Flow 2：旁白生成 → 串流播放（核心體驗）

```text
Flutter App                                    Cloud Run                          Gemini
   │                                              │                                  │
   │ POST /narration {poi, persona, lang}         │                                  │
   ├─────────────────────────────────────────────→│ NarrationCache.get(key)?         │
   │                                              │   命中 → stream 既有音訊          │
   │                                              │   未中 ↓                         │
   │                                              │ PromptBuilder.build()            │
   │                                              │ ConfidenceClassifier.classify()  │
   │                                              │ LlmProvider.chat_stream()        │
   │                                              ├─────────────────────────────────→│
   │                                              │ ←── text chunk                   │
   │                                              │ SentenceSplitter (邊收邊切)      │
   │                                              │ TtsProvider.synthesize(sentence) │
   │                                              ├─────────────────────────────────→│
   │                                              │ ←── audio bytes                  │
   │ ←── SSE: meta {confidence:"medium",...}      │                                  │
   │ ←── SSE: text {chunk:"故宮博物院..."}         │                                  │
   │ ←── SSE: audio {chunk_b64,sentence_idx:0}    │                                  │
   │   AudioPlayer.enqueue(chunk)                 │                                  │
   │   播放器一拿到第一塊就開始播 (~2 秒)          │                                  │
   │ ←── SSE: text + audio 持續...                 │                                  │
   │ ←── SSE: end                                 │                                  │
   │                                              │ NarrationCache.put(key, audio)   │
   │                                              │ LocalDB.history.add(...)         │
   │                                              │ LocalDB.cooldown.set(poi, 24h)   │
```

關鍵設計點：
- 後端 SSE 流交錯送 `audio` + `text` 兩種 event：文字用顯示同步字幕，音訊餵給播放器
- 第一塊音訊送出時 LLM 還在生成 → **首字延遲 ~2 秒**
- 後端**邊串流邊累積**完整音訊，串完寫入 NarrationCache（下次同條件秒回）

### 5.3 Flow 3：使用者按「我想問」（push-to-talk Q&A）

```text
使用者              Flutter App                    Cloud Run                    Gemini
  │                   │                              │                            │
  │ 按住「問」按鈕     │ MicRecorder.start()          │                            │
  ├──────────────────→│ AudioPlayer.duck() (旁白音量降50%)                        │
  │ "這個館為什麼這麼重要？"                          │                            │
  │ 放開按鈕          │ MicRecorder.stop()           │                            │
  ├──────────────────→│ POST /qa {audio, ctx}        │                            │
  │                   ├─────────────────────────────→│ SttProvider.transcribe()   │
  │                   │                              ├───────────────────────────→│
  │                   │                              │ ←── "這個館為什麼這麼重要？" │
  │                   │                              │ PromptBuilder.qa()         │
  │                   │                              │ LlmProvider.chat_stream()  │
  │                   │                              ├───────────────────────────→│
  │                   │                              │ → SentenceSplitter → TTS  │
  │                   │ ←── SSE: transcript+text+audio                            │
  │                   │   AudioPlayer.enqueue()      │                            │
  │                   │   (旁白佇列暫停，問答先播)   │                            │
  │                   │ 問答播完 → AudioPlayer.unduck() → 旁白繼續                │
```

關鍵設計點：
- 提問期間**旁白 ducking**（音量降 50%）而不是暫停 → 沉浸感不破
- 問答音訊播放優先級 > 旁白佇列
- 問答**不快取**（每次提問都不同）
- QA 不影響 cooldown / history

### 5.4 Flow 4：多 POI 排隊 + 走出範圍

```text
時間軸 →

t=0   進入故宮 100m 範圍 → 觸發 A
       Queue: [A]，播放 A 開始 (預估 2 分鐘)

t=30s 進入順益博物館 100m 範圍 → 觸發 B
       Queue: [A 播放中, B 排隊]
       UI 顯示：「下一站：順益台灣原住民博物館」

t=60s 使用者離開故宮 100m 範圍
       A 仍在播（D1: 繼續播完）

t=120s A 播完 → 自動接 B
       cooldown.set(A, 24h); history.add(A)

t=180s 使用者按「跳過」
       AudioPlayer.skip()
       cooldown.set(B, 24h)（聽過一部分也算）
       Queue 為空 → 等下一次觸發
```

---

## 6. 後端 API 設計

四個 endpoint，全走 HTTPS。串流的兩個用 SSE，單純 JSON 的兩個是 REST。所有 endpoint 都需要 `X-API-Key` header。

### 6.1 `GET /poi/nearby`

**Request**:
```text
GET /poi/nearby?lat=25.1023&lon=121.5482&radius=500&lang=zh-TW&persona=history_uncle
```

**Response (200)**:
```json
{
  "pois": [
    {
      "id": "osm:way:12345",
      "name": "國立故宮博物院",
      "name_localized": "國立故宮博物院",
      "lat": 25.1023,
      "lon": 121.5482,
      "tags": { "tourism": "museum", "historic": "yes" },
      "wiki": {
        "title": "國立故宮博物院",
        "extract": "國立故宮博物院位於...",
        "url": "https://zh.wikipedia.org/wiki/..."
      },
      "distance_m": 87,
      "confidence": "high"
    }
  ],
  "queried_at": "2026-05-08T03:15:42Z"
}
```

食家 persona 的回應額外含 `rating`, `user_ratings_total`, `price_level`, `cuisine`, `top_review_phrases`。

**錯誤**：
- `400` 座標格式錯誤
- `429` 上游限流（回 `Retry-After`）
- `503` 上游暫時不可用

### 6.2 `POST /narration` (SSE streaming)

**Request**:
```json
POST /narration
Accept: text/event-stream

{
  "poi_id": "osm:way:12345",
  "persona": "history_uncle",
  "lang": "zh-TW",
  "length": "medium",
  "force_regenerate": false
}
```

**Response (200, `text/event-stream`)**:
```text
event: meta
data: {"poi_id":"osm:way:12345","cache_hit":false,"confidence":"high","estimated_duration_s":120}

event: text
data: {"chunk":"故宮博物院位於台北市士林區，"}

event: audio
data: {"chunk_b64":"<base64-mp3>","sentence_idx":0}

event: text
data: {"chunk":"始建於 1925 年..."}

event: audio
data: {"chunk_b64":"<base64-mp3>","sentence_idx":1}

event: end
data: {"total_duration_s":118,"sentences":12}
```

**錯誤事件**：
```text
event: error
data: {"code":"llm_rate_limit","message":"...","retry_after_s":30}
```

### 6.3 `POST /qa` (SSE streaming, audio upload)

**Request** (multipart):
```text
POST /qa
Content-Type: multipart/form-data

audio: <wav/m4a binary>
context: {
  "current_poi_id": "osm:way:12345",
  "persona": "history_uncle",
  "lang": "zh-TW",
  "narration_so_far": "..."
}
```

**Response**:
```text
event: transcript
data: {"text":"這個館為什麼這麼重要？"}

event: text
data: {"chunk":"啊，這問得好..."}

event: audio
data: {"chunk_b64":"...","sentence_idx":0}

event: end
data: {"total_duration_s":18}
```

### 6.4 `GET /health`

```text
GET /health → 200 {"status":"ok","uptime_s":3600}
```

### 6.5 設計原則收斂

- **Streaming 一致性**：兩個 streaming endpoint 用同樣 SSE event 結構（`meta`/`text`/`audio`/`end`/`error`），client 共用 SSE parser
- **錯誤模型統一**：所有 error 都有 `code` + `message` + 可選 `retry_after_s`
- **無狀態**：每個 request 完整自帶 context（POI、persona、語言），重啟無痛
- **Versioning**：未來破壞性改動走 `/v2/...`，第一版 path 不加 `/v1/`
- **CORS / Auth**：v1 自用 → 無 CORS、無 auth；但有 `X-API-Key` 輕量保護避免 URL 外流被刷
- **音訊用 base64 in SSE**：SSE 規範限 text-only；多 33% 體積換簡化解析（v1 acceptable）

---

## 7. 資料模型

### 7.1 裝置端 SQLite Schema (drift)

```sql
-- 設定（單列、整體 transaction 更新）
CREATE TABLE settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  trigger_radius_m INTEGER NOT NULL DEFAULT 100,
  search_radius_m INTEGER NOT NULL DEFAULT 500,
  cooldown_hours INTEGER NOT NULL DEFAULT 24,
  narration_length TEXT NOT NULL DEFAULT 'medium',   -- short | medium | long
  default_persona TEXT,                              -- 可為 null（強制每次選）
  default_lang TEXT NOT NULL DEFAULT 'zh-TW',        -- zh-TW | en
  api_base_url TEXT NOT NULL,
  api_key TEXT NOT NULL
);

-- 旅程 session 紀錄
CREATE TABLE sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at INTEGER NOT NULL,
  ended_at INTEGER,
  persona TEXT NOT NULL,
  lang TEXT NOT NULL,
  trigger_radius_m INTEGER NOT NULL,
  start_lat REAL,
  start_lon REAL
);

-- 旁白播放紀錄（cooldown + 歷史）
CREATE TABLE narration_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  poi_id TEXT NOT NULL,
  poi_name TEXT NOT NULL,
  poi_lat REAL NOT NULL,
  poi_lon REAL NOT NULL,
  persona TEXT NOT NULL,
  lang TEXT NOT NULL,
  played_at INTEGER NOT NULL,
  duration_played_s INTEGER NOT NULL,
  completed INTEGER NOT NULL,
  triggered_by TEXT NOT NULL                          -- auto | manual_replay | manual_pick
);

CREATE INDEX idx_narration_poi_time ON narration_history(poi_id, played_at DESC);
CREATE INDEX idx_narration_session ON narration_history(session_id);

-- 本地音訊快取
CREATE TABLE tts_audio_cache (
  cache_key TEXT PRIMARY KEY,                         -- "{poi_id}|{persona}|{lang}|{length}"
  file_path TEXT NOT NULL,
  file_size_bytes INTEGER NOT NULL,
  text_transcript TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  last_accessed_at INTEGER NOT NULL
);
```

Cooldown 查詢：
```sql
SELECT 1 FROM narration_history
WHERE poi_id = ?
  AND played_at > ?  -- now_ms - cooldown_hours * 3600_000
LIMIT 1;
```

LRU cleanup（tts_audio_cache）：每次 app 啟動跑，保留最近 access 的 50 筆 或 200MB（取較嚴格者）。

### 7.2 後端檔案系統快取

#### POICache
- 兩層 key：
  - 區域層：`geo:{lat_grid_3dp}:{lon_grid_3dp}:{lang}`（≈100m 網格），TTL 30 天
  - POI 層：`poi:{poi_id}:{lang}`，TTL 30 天
- 存於 Cloud Run 容器 `/tmp/cache/`，重啟會掉
- 大小上限 100 MB（簡單 LRU）

#### NarrationCache
- Key：`narration:{poi_id}:{persona}:{lang}:{length}`
- 存於 `/tmp/narration_cache/`
- **重要 caveat**：Cloud Run scale-to-zero 會清 `/tmp` → 第一次冷啟動快取會掉
  - v1 acceptable：自用情境下沒打中只是多吃配額
  - v2 升級：改用 GCS bucket（持久、跨實例共享）
- 大小上限 500 MB

### 7.3 隱私與資料保留

| 資料 | 存哪 | 多久 | 備註 |
|---|---|---|---|
| 即時位置 | 不持久化 | session 期間在記憶體 | session 結束就清 |
| Session 起點座標 | 裝置 SQLite | 永久（直到使用者刪） | 「我的旅程」用 |
| narration_history | 裝置 SQLite | 永久（直到使用者刪） | 含當時的 POI 座標 |
| 後端 logs | Cloud Logging | 30 天（Cloud Run 預設） | **不 log 完整座標**，只 log 經緯度小數 1 位（~10km 精度） |
| Gemini API 輸入 | Google（**free tier 用於訓練**） | Google policy | v1 自用 acceptable，公開時須切付費 |

設定頁需提供「清除所有歷史」「清除快取」按鈕。

---

## 8. Persona 系統與多語策略

### 8.1 Persona 資源檔結構

每個 persona 是一個 YAML 檔（`prompts/personas/{id}.yaml`），程式碼不需要改，重新載入資源即可調整 prompt。

```yaml
id: history_uncle
display_name:
  zh-TW: 歷史大叔
  en: The History Uncle
description:
  zh-TW: 沉穩深度，年代典故脈絡清楚
  en: Calm and deep, weaving timelines and cultural context

voice:
  zh-TW: Charon
  en: Charon
voice_style:
  speaking_rate: 0.95
  emotion: contemplative

style_profile:
  embellishment: 0.1            # 0=只講有出處 / 1=愛加油添醋
  preferred_topics:
    - history
    - cultural_context
  speech_quirks:
    - "根據文獻記載"
    - "在那個年代"
    - "順帶一提"

poi_source: osm_wikipedia       # osm_wikipedia | google_places

system_prompt:
  zh-TW: |
    你是一位精通歷史的中年男性導遊，叫做「歷史大叔」。
    （詳細風格規範...）

narration_template:
  zh-TW: |
    {system_prompt}
    請根據以下資料以你的口吻介紹「{poi_name}」。
    {poi_context}
    要求：3 段 / 總長 {target_length} / 嚴禁編造未在背景資料中的具體年代、人名、數字 / ...

qa_template:
  zh-TW: |
    {system_prompt}
    使用者目前在「{poi_name}」附近，已聽過你的旁白（摘要：{narration_summary}）。
    使用者問：「{user_question}」
    請以「歷史大叔」的口吻簡短回答（30-60 秒）。如果超出 POI 範圍或知識邊界，誠實說「這我不太確定」並引導回 POI 本身。

system_messages:
  zh-TW:
    network_offline:
      - "嗯...連線出了點狀況，稍待片刻。"
    rate_limit:
      - "嗓子要稍微歇歇，再 30 秒..."
    location_blocked:
      - "你還沒讓我看你在哪兒，這可不行。請到設定打開定位權限。"
    permission_foreground_only:
      - "目前的權限只能在前景看到你。鎖屏後我就脫線了，請改為『一律允許』以享受完整旅程。"
    poi_in_cooldown:
      - "這個我前不久才剛跟你提過。要再聽一次嗎？"
    no_nearby_poi:
      - "這附近暫時沒有我熟悉的景點。"
    qa_out_of_scope:
      - "這部分我並不確定，但回到我們眼前這個地方..."
    session_killed_resume:
      - "上次的旅程沒有正常結束。要繼續嗎？"

confidence_labels:
  zh-TW:
    high: null
    medium:
      - "⚠ 此處資料偏少，大叔僅憑可查證的脈絡推測"
    low:
      - "⚠ 此處史料有限，大叔僅作脈絡推測，請勿引用"
```

### 8.2 五個 Persona 規格摘要

| Persona | 風格 | embellishment | 中文 voice | 英文 voice | speaking_rate | poi_source |
|---|---|---|---|---|---|---|
| **故事大哥哥** `story_brother` | 鄉間軼事派 | 0.6 | Puck | Puck | 1.05 | osm_wikipedia |
| **歷史大叔** `history_uncle` | 嚴謹考據派 | 0.1 | Charon | Charon | 0.95 | osm_wikipedia |
| **八卦阿姨** `gossip_auntie` | 名人八卦派 | 0.5 | Aoede | Aoede | 1.0 | osm_wikipedia |
| **童趣小妹** `kid_sister` | 好奇驚嘆派 | 0.3 | Kore | Kore | 1.0 | osm_wikipedia |
| **美食家** `foodie` | 食物推薦派 | 0.4 | Leda | Leda | 1.0 | google_places |

各 persona 的 `system_messages` / `confidence_labels` 都是該 persona 用自己的口吻講 — 同一個錯誤五個人會有完全不同的措辭，每個訊息可放多個變體 client 隨機選一個避免重複。

### 8.3 Confidence 判定與 UI 呈現

| 等級 | 判斷規則 | UI 呈現 |
|---|---|---|
| **high** | POI 有完整 Wikipedia 條目（intro section ≥ 200 字）<br>食家 persona：rating ≥ 4.5 + ≥ 100 評論 | 不顯示任何標籤 |
| **medium** | 有 wiki 但條目很短，或只有 OSM tag（強訊號）但無 wiki<br>食家：rating 4.3-4.5 或評論 50-100 | 旁白播放畫面底部顯示 persona 的 medium hedge（灰色小字） |
| **low** | 僅 POI 名稱 + 大致類型，無其他資訊 | 同 medium 但更明顯（persona 主題色 + emoji） |

判定責任在後端 `ConfidenceClassifier`，結果隨 SSE `meta` event 一併送 client。

### 8.4 多語策略

#### 旁白語言切換
- `lang` 參數 (`zh-TW` / `en`) 由 client 在每次 `/narration` 帶進來
- Backend `PromptBuilder` 依 `lang` 選對應的 `system_prompt` / `narration_template` / `system_messages` / `confidence_labels`
- TTS voice 也按 `lang` 從 persona `voice` map 取
- **不做即時翻譯**：每個 persona 的中英 prompt 都是手寫，避免「中翻英」的不自然感

#### Wikipedia 內容的語言處理
- 使用者選 `zh-TW` → 優先抓中文版條目；無中文版時 fallback 抓英文版，prompt 中明確指示「來源是英文資料，請用中文重新組織」
- POI 的 wikidata tag 是跨語言通用的，可以一次拿到所有語言版本連結

#### POI 名稱顯示
- OSM 的 `name:zh` / `name:en` tag 提供本地化名稱
- 沒對應語言 tag 時，fallback 到 `name`（原語言）+ `int_name`（國際化拼音）

#### App UI i18n
- Flutter 用 `flutter_localizations` + `arb` 檔案
- 兩個 `.arb`：`app_zh_TW.arb`、`app_en.arb`
- 第一次啟動依 device locale 自動選；之後遵循 `settings.default_lang`

### 8.5 食家 persona 觸發邏輯特化

```text
TriggerEngine
  ↓ 當前 persona == foodie?
  ├─ 否：照舊（Overpass tourism/historic + Wiki tag）
  └─ 是：改走 Google Places Nearby (type=restaurant|cafe|bakery)
        ├─ 評分過濾：rating ≥ 4.3 且 user_ratings_total ≥ 50
        ├─ 用餐時段加權：11-14 / 17-21 內門檻降到 4.0 / 30 評論
        ├─ 觸發半徑：見下方「半徑解析規則」
        ├─ Cooldown：照舊 24h
        └─ 連鎖識別：Google Places types 含 food_chain 時，旁白會提及
```

#### 觸發半徑解析規則（per-persona override）

每個 persona YAML 多一個欄位 `default_trigger_radius_m`：
```yaml
default_trigger_radius_m: 50    # foodie: 50；其他 persona: 100
```

實際生效半徑的解析順序（TriggerEngine 採用）：
1. 若使用者在 settings 頁明確調整過該 persona 的半徑（per-persona override，存於 `settings_persona_overrides` 表）→ 用該值
2. 否則 → 用 persona YAML 的 `default_trigger_radius_m`
3. 若 persona YAML 沒設 → fallback 到 `settings.trigger_radius_m`（全域預設 100）

對應的裝置端 schema 增補：
```sql
CREATE TABLE settings_persona_overrides (
  persona TEXT PRIMARY KEY,            -- e.g. 'foodie'
  trigger_radius_m INTEGER             -- null 表示用 persona YAML 預設
);
```

UI：設定頁的 slider 顯示「目前 persona 的觸發半徑」，並標註「（食家預設 50m / 其他預設 100m）」。

### 8.6 Prompt 版本管理

- Persona YAML 檔放 git，每次改 prompt 都是一個 commit，可以 review
- Backend 啟動時讀檔載入記憶體（不需要每次 request 讀檔）
- 提供 `POST /admin/reload-prompts` endpoint（保護在 `X-API-Key` 後）讓不用重啟容器就能重載

---

## 9. 錯誤處理與邊界情況

### 9.1 失敗等級

按嚴重度分四級，每級的處理態度：

1. **L1 完全致命**（無定位權限、API key 錯誤）：阻擋 + 引導修復
2. **L2 功能受損**（無網路、Gemini 限流）：通知使用者 + 自動重試 + 部分功能仍可用
3. **L3 體驗瑕疵**（POI 資料弱、單句 TTS 失敗）：靜默 fallback + log 但不打擾使用者
4. **L4 預期狀態**（cooldown、無相關 POI）：不算錯誤，正常 UI 表示

### 9.2 通用原則

- **錯誤訊息全 persona 化**：不顯示「正在連線」這種無趣系統文字，而是當前 persona 的口吻（取自 `system_messages` YAML）
- **重試策略**：BackendClient 內建指數退避（1s / 2s / 4s）3 次
- **降級而非阻擋**：能繼續用就繼續用（離線時 pending queue、TTS 單句失敗時跳過）

### 9.3 網路 / 服務類

| 情境 | 行為 | UX |
|---|---|---|
| 完全無網路 | TriggerEngine 暫停查詢，仍偵測位置；觸發到 POI 靜默記到 pending | 狀態列顯示「離線中」；恢復網路後 prompt「剛才你經過 X，要補聽嗎？」 |
| 後端 5xx / 冷啟動 | BackendClient 重試 3 次（1s/2s/4s） | 第二次起顯示 persona 化的「連線中」訊息 |
| Gemini rate limit (429) | 後端回 SSE `error` event with `retry_after_s` | UI 用 persona 口吻倒數，倒完自動重試 |
| Overpass / Wikipedia 暫不可用 | POIService 回 503 | 同「離線」處理 |
| SSE 串流中途斷線 | AudioPlayer 播完已 enqueue 部分後停止；BackendClient 自動重試 1 次 | persona 訊息「連線中斷，正在重試」；重試成功從頭播 |
| TTS 合成單句失敗 | 後端跳過該句繼續下一句 | 字幕仍有文字、該句沒有音訊；不中斷整段播放 |

### 9.4 位置 / 權限類

| 情境 | 行為 | UX |
|---|---|---|
| 未授予定位權限 | SessionController.start() 拒絕 | 跳引導頁面 + 直達設定按鈕 |
| 僅授予「使用 App 期間」 | 前景能跑，鎖屏停止 | session 啟動時用 persona 口吻提示「鎖屏後我會脫線，要享受完整體驗請改為一律允許」 |
| 背景定位被系統暫時停掉 | 嘗試重啟 → 失敗則發 notification | 通知列「導覽已暫停，點擊恢復」 |
| 使用者半路撤回權限 | 收到 platform event → SessionController.stop() | persona 訊息 + 重新授權連結 |
| GPS 訊號差（精度 > 100m） | TriggerEngine 不評估觸發 | 狀態列「定位精度不足」 |

### 9.5 內容品質類

| 情境 | 行為 | UX |
|---|---|---|
| POI 無 Wikipedia 但 OSM tag 強 | LLM 用 OSM tags 自由生成；prompt 加註「資料有限，請保守敘述」 | confidence 標為 medium → 顯示 persona 的 medium hedge 標籤 |
| Wikipedia 條目是消歧義頁面 | 視為無條目 | 同上 |
| Wikipedia 摘要太長 (>3000 字) | PromptBuilder 截斷至前 1500 字 + intro section | 無感 |
| LLM 包含明顯幻覺 | 透過 prompt 強制 hedging + confidence 標籤；後端 sanity check（年代 > 當年則疑慮） | 不抑制創作；UI 標籤誠實標明「這可能是 [persona] 自己胡謅的」 |

### 9.6 音訊 / 提問類

| 情境 | 行為 | UX |
|---|---|---|
| 嘈雜環境提問 STT 信心低 | 仍嘗試；prompt 加註「轉錄結果可能不準確，請優雅澄清」 | 字幕顯示轉錄結果，使用者必要時重問 |
| 問完全無關問題 | LLM persona prompt 規定「超出範圍誠實說『這我不太確定』並引導回 POI」 | persona 自然回答不破角色 |
| 按住「問」沒講話就放開（< 0.5s） | MicRecorder 不送出，靜默取消 | 無動作 |
| 無旁白播放時提問 | QA endpoint 收到 `current_poi_id = null`，prompt 改為「使用者主動發問，請以 persona 口吻自然回答」 | 可問通用問題 |
| 問答播放時又按提問鈕 | 取消當前問答 + 重新錄音 | 自然支援「插話更正」 |
| TTS 音訊隊列堵塞 | AudioPlayer 進入「等待中」狀態 | 短暫 spinner，通常 < 2s |

### 9.7 使用者行為類

| 情境 | 行為 | UX |
|---|---|---|
| App 被系統 kill 但 session 進行中 | 重啟時偵測 `sessions.ended_at IS NULL` | persona 口吻 prompt「上次旅程沒結束，要繼續嗎？」 |
| 低電量模式 | LocationService 降低取樣頻率（10s → 30s） | Toast「低電量模式，AI 反應可能較慢」 |
| 同 session 走重複路線 | session-level dedup 已處理 | 無提示 |
| Cooldown 中走過 POI | 自動觸發跳過；附近清單會列出但標註「N 小時內聽過」 | 可手動點「再講一次」override 但不重置 cooldown |
| 設定值被改成不合理數字 | drift schema CHECK 約束 + app 啟動時 validate | 不合理值自動 reset 為 default |

### 9.8 進階：「再來一個版本」

既然幻覺當特色，提供：
- **「同 persona 再講一次」**：強制 cache miss，每次內容會不同
- **「換個 persona 再講一次」**：直接體驗同地點不同視角

兩個按鈕在旁白播完的尾頁很自然存在。

---

## 10. 測試策略

### 10.1 測試金字塔

```text
                    ┌──────────────────┐
                    │ Manual / Real    │  GPS、麥克風、背景定位、TTS 真實聽感
                    │ Device E2E       │  維護「QA scenarios」清單
                    └──────────────────┘
                ┌──────────────────────────┐
                │ Integration Tests         │  API endpoint + 假 provider
                │ (Backend + Flutter)       │  drift DB schema migration
                └──────────────────────────┘
        ┌────────────────────────────────────────┐
        │ Unit Tests (70%+)                       │  純函式 + 狀態機
        │ • SentenceSplitter, TriggerEngine       │  provider abstraction 讓 test 簡單
        │ • PromptBuilder, POI filter             │
        │ • Cooldown logic, Audio queue           │
        └────────────────────────────────────────┘
```

### 10.2 後端測試（Python / pytest）

#### Unit tests（最大宗）
| 模組 | 測試什麼 |
|---|---|
| `SentenceSplitter` | 中英文混合句子的切分邊界 |
| `PromptBuilder` | 不同 persona / lang 組出的訊息結構 |
| `POI filter` | whitelist tag、wiki tag、熱門度判斷 |
| `ConfidenceClassifier` | high/medium/low 判定規則 |
| `CooldownChecker` | 給時間 + history → 是否觸發 |
| `POICache / NarrationCache` | LRU、TTL、key 計算 |

#### Provider 測試替身
每個 provider 都有 fake：
```python
class FakeLlmProvider(LlmProvider):
    def __init__(self, scripted_chunks: list[str]): ...
    async def chat_stream(self, messages, opts):
        for c in self.chunks: yield c

class FakeTtsProvider(TtsProvider):
    """Returns a fixed silent mp3 chunk for any input."""

class FakeSttProvider(SttProvider):
    def __init__(self, scripted_text: str): ...
```
→ 任何用到 provider 的測試都不打 Gemini，**完全離線、零成本**。

#### Integration tests
- FastAPI `TestClient` + 全套 fake provider
- 測 `/poi/nearby`、`/narration` SSE 串流順序、`/qa` multipart 上傳
- 測 SSE error event 在 rate limit 時的傳遞
- 測 cache 命中時的 short-circuit

#### 真實 provider smoke tests（手動觸發）
- 標記 `@pytest.mark.real_provider`
- 預設 CI 不跑（會花錢）
- `pytest -m real_provider` 才跑，驗證 LiteLLM model 字串、Gemini API 變動

### 10.3 Flutter App 測試

#### Unit tests
| 模組 | 測試什麼 |
|---|---|
| `TriggerEngine` | 給座標串流 + POI 列表 → 觸發事件序列（純函式，最易測） |
| `SessionController` | 狀態機：idle → starting → active → ending |
| `AudioPlayer` queue 邏輯 | enqueue / pause / skip 順序、ducking 行為 |
| `PromptCacheKey` 計算 | (poi, persona, lang) 組合與 hash 一致性 |

#### Widget tests
- PersonaPicker、設定頁的 slider、status indicator 顯示

#### Drift DB 測試
- 用 in-memory SQLite (`NativeDatabase.memory()`)
- 驗證 schema migration、cooldown query 的 SQL 正確性

#### 假後端
`FakeBackendClient implements BackendClient`：
- 模擬 SSE event 順序（meta → text → audio → end）
- 模擬 error event、連線中斷
- 讓 `NarrationOrchestrator` 完全離線測試

### 10.4 真機手測（無法繞過）

維護 `QA_SCENARIOS.md`，每次發版前跑一次：

| 場景 | 測什麼 |
|---|---|
| 步行進入 POI 觸發半徑 | 觸發時機、首字延遲、音訊連續性 |
| 鎖屏走路 | 背景定位是否持續、AI 是否在鎖屏狀態繼續講 |
| 切換 App（聽 podcast 中） | 音訊衝突處理、回到 App 時的恢復 |
| 半路撤回定位權限 | 提示是否清楚、是否能復原 |
| 飛航模式中觸發 POI | pending queue、恢復網路後的補聽 prompt |
| Push-to-talk 提問 | 各種環境噪音、ducking 體驗 |
| 切換 5 個 persona 各一次 | voice 差異、口吻、confidence 標籤是否符合 |
| 走過已 cooldown 的 POI | 自動跳過、手動可 override |
| 食家 persona 在用餐 / 非用餐時段 | 評分門檻調整是否生效 |

### 10.5 TDD 執行節奏

依 CLAUDE.md 的 red-green-refactor，每個 module 起手式：

1. **Red**：先寫 1-2 個 critical-path test（會失敗）
2. **Green**：寫最小實作讓測試過
3. **Refactor**：抽出共用、整理命名
4. 加邊界 case 測試 → 補實作

特別適合 TDD 的順序（依複雜度遞增）：
1. `SentenceSplitter` (純函式，暖手用)
2. `PromptBuilder` (純資料組裝)
3. `POI filter / ConfidenceClassifier`
4. `CooldownChecker`
5. `TriggerEngine`
6. 之後才碰 IO（cache 用 tmp dir、API 用 TestClient）

provider 介面設計時就**先設計 fake**，這樣所有上層都能 TDD。

### 10.6 不做的測試（YAGNI）

- TTS 音訊內容的對比測試（音訊主觀，難自動化）
- LLM 輸出語意正確性的 assertion（會 flaky，留給人工 spot check）
- E2E with real GPS simulation（太脆弱，真機跑就好）
- Load test（v1 自用沒意義）
- Cross-browser test（不適用）

---

## 11. 技術棧細節

### 11.1 後端

| 用途 | 套件 |
|---|---|
| Web framework | FastAPI |
| ASGI server | uvicorn |
| LLM 抽象 | litellm |
| Gemini SDK | google-genai |
| HTTP client | httpx |
| 設定 | pydantic-settings |
| 測試 | pytest, pytest-asyncio, freezegun, respx |
| 容器化 | Dockerfile（python:3.12-slim base） |
| 部署 | Cloud Run (gcloud run deploy) |

### 11.2 Flutter App

| 用途 | 套件 |
|---|---|
| 定位 | geolocator |
| 背景定位 | flutter_background_geolocation 或 geolocator + 平台原生設定 |
| 音訊播放 | just_audio |
| 音訊錄製 | record |
| HTTP / SSE | dio + 自寫 SSE parser，或 fetch_client + sse_stream |
| 本地 DB | drift |
| 狀態管理 | riverpod |
| i18n | flutter_localizations + intl + arb 檔 |

### 11.3 開發環境

- 後端：本地 `uvicorn main:app --reload`，配合 fake providers 完全離線
- App：`flutter run` 對接本地後端 (`http://10.0.2.2:8000` for Android emulator, `http://localhost:8000` for iOS simulator)
- 真機測試：後端先部署到 Cloud Run staging，App 切到 staging URL

### 11.4 部署流程

1. 後端：`docker build` → `gcloud run deploy ai-tour-guide-backend --region asia-east1`
2. App：iOS 走 TestFlight，Android 走 internal testing
3. v1 自用：兩者都不上 store，sideload 到自己手機即可

---

## 12. v1 範圍外（明確不做）

- 使用者帳號 / 跨裝置同步
- 社群分享（聽過哪些景點）
- 客製 persona（使用者自己寫 prompt）
- ElevenLabs / OpenAI TTS / Claude LLM swap（保留架構，不在 v1 實作）
- 離線旁白生成（v1 完全 online）
- 系統 geofence 觸發（用 polling-based）
- 推播通知 / FCM
- 完整字幕同步（v1 字幕僅文字，不時間對齊）
- 查詢半徑 UI 暴露（內部固定 500m）
- 句子層級 confidence 標籤（v1 整段一個 confidence）
- POI 圖片顯示（v1 純文字 + 音訊）
- 「我的旅程」資料視覺化（schema 已存好，v1 無頁面）

---

## 13. 後續版本路線（不承諾，僅參考）

### v1.1
- ElevenLabs TTS swap（提升 persona voice 表現力）
- GCS bucket 化 NarrationCache（解決冷啟動快取丟失）
- 「我的旅程」history 頁面 + 簡單統計

### v1.2
- 客製 persona（使用者自己寫 prompt）
- 推播通知（離線時觸發 → 線上時補通知）

### v2
- 使用者登入 / 多人 / 配額管理
- 切 Gemini 付費版（資料不被訓練）或 Claude
- 系統 geofence 觸發（極省電）
- 社群功能（分享、推薦）
- POI 圖片 + 完整字幕時間對齊

---

## 14. 開放問題 / 待研究項目

實作階段需驗證：

- Gemini 2.5 Flash TTS 內建 30 個 voice 的中英文表現是否足以區分 5 個 persona（特別是 Aoede / Leda / Kore 三位女聲是否夠有差別感）
- LiteLLM 對 Gemini 的 streaming API mapping 是否穩定（可能要回退到原生 google-genai SDK）
- iOS Background Modes `location` 在 App 被系統 kill 後的喚醒行為（可能需要結合 region monitoring）
- Overpass 公共伺服器在自用流量下是否需要自架 mirror（v1 應該不需要）
- Google Places `nearbysearch` 對 `type=restaurant` 與 `cuisine` 的精確度（v1 食家 persona 的核心依賴）

---

## 文件結束
