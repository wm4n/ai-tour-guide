# Session Handoff — AI Tour Guide

> 這份文件給下一個 Claude session 用，目的是讓對方在 zero context 下能直接接手繼續推進。

**前次 session 結束時間**：2026-05-12
**前次 session 主要產出**：Plan C Persona 系統擴充完成，Flutter 53/53 測試通過，後端 145/146 通過（1 個既有 TTL 測試與 Plan C 無關），flutter analyze 無 error

---

## 1. 專案總覽

可帶出門的 AI tour guide 行動 App。使用者按「開始旅程」+ 選 persona（角色）後，App 在前景偵測位置；走進景點 100m 範圍時，AI 自動以該 persona 的口吻串流播報旁白；可隨時 push-to-talk 提問。

技術棧：
- **Backend**：Python 3.12 / FastAPI / LiteLLM / google-genai / pytest（在 `backend/` 目錄）
- **App**：Flutter 3.x / Dart 3.x（在 `flutter_app/` 目錄）
- **AI 服務 v1**：全 Gemini free tier（LLM / TTS / STT）
- **POI 來源**：OSM Overpass + Wikipedia
- **部署 v1**：Cloud Run（Plan F 才開始部署）

完整設計：`docs/superpowers/specs/2026-05-08-ai-tour-guide-design.md`

---

## 2. 漸進式 6 個 Plan 路線

| Plan | 名稱 | 狀態 | 文件 |
|---|---|---|---|
| **A** | Backend MVP — 單 persona narration | ✅ **完成** | `docs/superpowers/plans/2026-05-08-plan-a-backend-mvp.md` |
| **B** | Flutter App MVP — 消費 Plan A 後端 | ✅ **完成** | `docs/superpowers/plans/2026-05-11-plan-b-flutter-app-mvp.md` |
| **C** | Persona 系統擴充 + 雙語（5 persona、zh-TW + en） | ✅ **完成** | `docs/superpowers/plans/2026-05-12-plan-c-persona-i18n.md` |
| **D** | Push-to-talk Q&A | 未開始 | 待寫 |
| **E** | 食家 persona + Google Places | 未開始 | 待寫 |
| **F** | 背景定位 + 部署上線 | 未開始 | 待寫 |

---

## 3. 目前進度

### Plan A — Backend MVP（已完成）

最後幾個關鍵 commit：
```
11d19fa fix(backend): move noqa S108 comments to correct lines in config.py
729c92d feat(backend): add smoke tests and complete README with curl recipes
83bf0c1 chore(backend): full test suite passes, lint and format clean
8002b66 feat(backend): add FastAPI app factory with full DI wiring (TDD)
f949fc6 feat(backend): add LiteLLMAdapter and GeminiTtsAdapter real provider implementations
```

Backend 驗證方式：
```bash
cd backend && .venv/bin/pytest -v           # 全部綠燈
cd backend && .venv/bin/ruff check src/     # 乾淨
curl http://localhost:8000/health           # {"status":"ok"}
```

### Plan B — Flutter App MVP（已完成）

**最後狀態**：42/42 tests pass，flutter analyze 7 個 info（`prefer_const_constructors`、`use_super_parameters`），無 error/warning

### Plan C — Persona 系統擴充 + 雙語（已完成）

**最後狀態**：Flutter 53/53 tests pass，後端 145/146 pass（1 個既有 TTL 測試與 Plan C 無關），flutter analyze 無 error

Plan C 新增的關鍵 commits（由新到舊）：
```
967fe06 fix(flutter): update narrate() call sites in map_screen and narration_sheet_test with persona/lang params
319d365 feat(flutter): restructure HomeScreen with PersonaSelector cards and language toggle
668c26d feat(flutter): TriggerNotifier reads persona/lang from sessionProvider before narrating
adbfacd feat(flutter): narrate() accepts persona/lang params, reads from session state
165b1cc feat(flutter): add PersonaSelector vertical card widget with selection state
5a40f87 feat(flutter): expose persona/lang in SessionState.copyWith, add setPersona/setLang
3b3fa4b feat(flutter): add PersonaInfo model and kPersonas constants
f413896 feat(backend): wire PersonaLoader into /narration endpoint, unknown persona → 400
2f3fc53 feat(backend): add story_brother, gossip_auntie, kid_sister, foodie persona YAMLs
d4c3d7c feat(backend): add PersonaLoader.load_all() to load all persona YAMLs
```

---

## 4. Flutter App 架構（Plan C 產出）

```
flutter_app/lib/
├── main.dart                                  ← ProviderScope + runApp(App())
├── app.dart                                   ← MaterialApp.router + GoRouter (/ → Home, /map → Map)
├── features/
│   ├── session/
│   │   ├── persona_data.dart                  ← PersonaInfo model + kPersonas (5 個 persona 常數) [Plan C]
│   │   ├── providers/session_provider.dart    ← SessionNotifier + setPersona/setLang [Plan C 擴充]
│   │   ├── screens/home_screen.dart           ← PersonaSelector + SegmentedButton 語言切換 [Plan C 改版]
│   │   ├── widgets/persona_chip.dart          ← 已棄用（保留檔案但 HomeScreen 不再使用）
│   │   └── widgets/persona_selector.dart      ← 5 張垂直卡片選角 UI [Plan C]
│   ├── map/
│   │   ├── providers/poi_provider.dart        ← PoiNotifier (AsyncNotifier), 250m 重新 fetch
│   │   ├── screens/map_screen.dart            ← GoogleMap + POI markers + NarrationSheet overlay
│   │   └── widgets/poi_marker.dart            ← BitmapDescriptor 依 confidence (azure/yellow/red)
│   └── narration/
│       ├── trigger_engine.dart                ← 純靜態 TriggerEngine.evaluate()
│       ├── providers/narration_provider.dart  ← NarrationNotifier, narrate(poi, persona:, lang:) [Plan C 擴充]
│       ├── providers/trigger_provider.dart    ← TriggerNotifier, 從 sessionProvider 讀 persona/lang [Plan C]
│       ├── widgets/narration_mini_bar.dart    ← 底部 mini bar (playing/paused toggle + skip)
│       └── widgets/narration_sheet.dart       ← DraggableScrollableSheet (12% → 60%)
└── shared/
    ├── providers.dart                         ← backendClientProvider, locationServiceProvider, localDbProvider, audioPlayerServiceProvider
    ├── backend/
    │   ├── backend_client.dart                ← abstract BackendClient + RealBackendClient + FakeBackendClient
    │   ├── sse_parser.dart                    ← 純靜態 SseParser (text/event-stream → SseEvent)
    │   └── models/
    │       ├── poi.dart                       ← POI model (id, name, lat, lon, tags, confidence, distanceM)
    │       └── narration_event.dart           ← sealed NarrationEvent (Meta/Text/Audio/End/Error)
    ├── location/
    │   ├── haversine.dart                     ← 純函式 haversine(lat1, lon1, lat2, lon2) → metres
    │   └── location_service.dart              ← abstract LocationService + Real + Fake
    ├── audio/
    │   └── audio_player_service.dart          ← abstract AudioPlayerService + Real (just_audio) + Fake
    └── db/
        ├── local_db.dart                      ← Drift schema (sessions + narration_history)
        └── local_db.g.dart                    ← build_runner 產生（勿手動修改）
```

**重要 NarrationEvent 模型細節**（與 backend payload 對齊，勿隨意改動）：
- `EndEvent` — 無任何欄位，`const EndEvent()`
- `TextEvent` — 有 `sentenceIdx` 欄位
- `MetaEvent` — 有 `estimatedDurationS` 欄位
- 全部 subclass 有 `fromJson` factory

**Plan C 新增後端檔案：**
- `backend/prompts/personas/history_uncle.yaml` — 歷史大叔（既有，已補 en）
- `backend/prompts/personas/story_brother.yaml` — 故事大哥哥
- `backend/prompts/personas/gossip_auntie.yaml` — 八卦阿姨
- `backend/prompts/personas/kid_sister.yaml` — 童趣小妹
- `backend/prompts/personas/foodie.yaml` — 美食家
- `PersonaLoader.load_all()` 在 app startup 預載全部 persona 到 registry
- `/narration` endpoint 改從 registry 取 persona（unknown → 400）

**dart-define 注入**：
- `dart_defines/dev.json` → `{"BACKEND_URL": "http://10.0.2.2:8000"}` (Android emulator)
- iOS simulator 用 `--dart-define=BACKEND_URL=http://localhost:8000`

---

## 5. 下一步具體 action（依優先序）

### Step 1：端對端 smoke test（需要人工操作）

```bash
# 啟動後端
cd backend && GEMINI_API_KEY=<真實key> .venv/bin/uvicorn tour_guide.main:app --reload

# 跑 Flutter（Android Emulator）
cd flutter_app && flutter run --dart-define-from-file=dart_defines/dev.json
```

驗證 Plan C golden path：
1. HomeScreen 顯示 5 張 persona 卡片
2. 點選不同 persona → highlight 正確移動
3. 切換語言（中文/EN）
4. 點「開始旅程」→ 地圖開啟，POI markers 顯示
5. 走近 100m POI → 自動以選定 persona + 語言觸發旁白

### Step 2：Plan D — Push-to-talk Q&A

使用 brainstorming skill 設計 Plan D：
- 麥克風錄音（push-to-talk）→ Google STT → LLM（同 persona context）→ TTS
- 旁白 ducking（音量降 50%）而非暫停
- `/qa` SSE endpoint（後端已在設計文件中規劃好）
- 問答不快取、不影響 cooldown/history

---

## 6. 必須知道的 context

### 6.1 Google Maps API Key（尚未設定）

需要替換兩個佔位符：
- Android：`flutter_app/android/app/src/main/AndroidManifest.xml` → `YOUR_ANDROID_MAPS_API_KEY`
- iOS：`flutter_app/ios/Runner/AppDelegate.swift` → `YOUR_IOS_MAPS_API_KEY`

取得 key：Google Cloud Console → Maps SDK for Android + Maps SDK for iOS 啟用

### 6.2 GEMINI_API_KEY（尚未設定）

`backend/.env` 或 `export GEMINI_API_KEY=...`
取得：https://aistudio.google.com/apikey

所有 unit/widget/integration test 均用 fake，不需要真實 key。

### 6.3 Plan C 設計限制（MVP 有意為之，後續 Plan 擴充）

- `foodie` persona 的 Google Places POI 路由 → Plan E 範圍（Plan C 先走 osm_wikipedia）
- Flutter UI 文字 i18n（按鈕、對話框）維持中文 → Plan F 範圍
- persona 觸發半徑 per-persona override（foodie 預設 50m）→ Plan F 範圍
- `recordNarration(sessionId: 1, ...)` hardcoded — MVP 不強制 session FK
- `flutter analyze` 僅 info 等級，無 error/warning

### 6.4 Drift build_runner

如果修改 `local_db.dart` schema，需重跑：
```bash
cd flutter_app && dart run build_runner build --delete-conflicting-outputs
```

### 6.5 SubAgent 執行方式

本專案使用 `superpowers:subagent-driven-development` + `opsx:new` 做 Spec Driven Development。每個 task 走 fresh subagent → spec review → code quality review → mark complete 流程。

---

## 7. 關鍵檔案索引

| 用途 | 路徑 |
|---|---|
| 整體 v1 設計 | `docs/superpowers/specs/2026-05-08-ai-tour-guide-design.md` |
| Plan B Flutter App MVP 設計 | `docs/superpowers/specs/2026-05-11-plan-b-flutter-app-mvp-design.md` |
| Plan C Persona + 雙語設計 | `docs/superpowers/specs/2026-05-12-plan-c-persona-i18n-design.md` |
| Plan A Backend 實作計畫 | `docs/superpowers/plans/2026-05-08-plan-a-backend-mvp.md` |
| Plan B Flutter App 實作計畫 | `docs/superpowers/plans/2026-05-11-plan-b-flutter-app-mvp.md` |
| Plan C 實作計畫 | `docs/superpowers/plans/2026-05-12-plan-c-persona-i18n.md` |
| OpenSpec Plan C change（已 archive） | `openspec/changes/archive/2026-05-13-plan-c-persona-i18n/` |
| Persona YAML 檔案 | `backend/prompts/personas/` |
| Backend 程式碼 | `backend/src/tour_guide/` |
| Flutter App 程式碼 | `flutter_app/lib/` |
| Flutter App 測試 | `flutter_app/test/` |
| Flutter App README | `flutter_app/README.md` |
| 此 handoff 文件 | `tasks/session-handoff.md` |

---

## 8. 跟使用者互動的偏好

- 全程**繁體中文**對話（CLAUDE.md 全域規範）
- 偏好**簡潔回應 + 具體選項**（不要長篇 narrate）
- 推薦時**講清楚 trade-off + 推薦哪個 + 為什麼**，給使用者拍板
- 重要決策（commit、安裝、permission 變動）**先 propose 等確認**
- 使用 `superpowers:subagent-driven-development` 執行任何計畫

---

## 9. 給下一個 session 的開場 prompt 模板

```text
我想接續上次的 AI tour guide 專案進度。請先讀 tasks/session-handoff.md，
然後按其中「下一步具體 action」往下做。
Plan A（後端）、Plan B（Flutter App）、Plan C（Persona 系統 + 雙語）都已完成，
下一步是端對端 smoke test，然後開始 Plan D（Push-to-talk Q&A）。
```

—— END HANDOFF
