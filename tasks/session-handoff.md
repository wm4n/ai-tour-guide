# Session Handoff — AI Tour Guide

> 這份文件給下一個 Claude session 用，目的是讓對方在 zero context 下能直接接手繼續推進。

**前次 session 結束時間**：2026-05-14
**前次 session 主要產出**：Plan F 背景定位 + Cloud Run 部署上線完成，Flutter 84/84 測試通過，後端 199/199 通過，flutter analyze 無 error

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
| **D** | Push-to-talk Q&A | ✅ **完成** | `docs/superpowers/plans/2026-05-13-plan-d-push-to-talk.md` |
| **E** | 食家 persona + Google Places | ✅ **完成** | `docs/superpowers/plans/2026-05-14-plan-e-foodie-google-places.md` |
| **F** | 背景定位 + Cloud Run 部署上線 | ✅ **完成** | `docs/superpowers/plans/2026-05-14-plan-f-background-location-deploy.md` |

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

### Plan D — Push-to-talk Q&A（已完成）

**最後狀態**：Flutter 71/71 tests pass，後端 159/159 pass，flutter analyze 10 info（無 error/warning）

### Plan F — 背景定位 + Cloud Run 部署上線（已完成）

**最後狀態**：Flutter 84/84 tests pass，後端 199/199 pass，flutter analyze 無 error

Plan F 新增的關鍵 commits（由新到舊）：
```
88b5282 chore: mark all Plan F tasks complete in tasks.md
21809c1 docs: add prod.json.example and SETUP.md for production deployment guide
917e815 feat(scripts): add GCP setup and Cloud Run deploy scripts
3a6471a chore: update .gitignore and dart_defines for Plan F secrets
5cff8fd feat(ios): background location, MAPS_API_KEY_IOS via xcconfig
6356db0 feat(android): background location permissions, GeolocatorService, MAPS_API_KEY injection
9e71c2e feat(flutter): App widget lifecycle observer for background notification routing
d3209c2 feat(flutter): HomeScreen whileInUse background location SnackBar with TDD
673b1c8 feat(flutter): TriggerNotifier background routing with TDD
68d2468 feat(flutter): LocationService checkPermission() + Platform-aware background start()
1e28819 feat(flutter): add notificationServiceProvider, appLifecycleStateProvider, BackendClient X-Api-Key header
368de8d feat(flutter): add NotificationService with TDD
1fb3b3a feat(flutter): add flutter_local_notifications ^17.2.4 dependency
0b934ea feat(backend): add Dockerfile and .dockerignore for Cloud Run deployment
d43b125 feat(backend): add X-Api-Key middleware with TDD
```

### Plan E — 食家 persona + Google Places（已完成）

**最後狀態**：Flutter 77/77 tests pass，後端 195/195 pass（+2 skipped），flutter analyze 12 info（無 error/warning）

Plan E 新增的關鍵 commits（由新到舊）：
```
be1c4c8 feat(flutter): add _FoodieRatingBar to NarrationSheet — shows rating/price for foodie POIs
f6ee480 feat(flutter): TriggerNotifier reads per-persona trigger radius from kPersonas
4db18a5 feat(flutter): add defaultTriggerRadiusM to PersonaInfo; foodie=50m, others=100m
0b6b4a2 feat(flutter): extend POI model with nullable foodie fields (rating, priceLevel, etc.)
d905c2b feat(backend): wire GooglePlacesClient in app factory (env-var based Real/Fake switch)
a5e6d62 feat(backend): api/poi.py conditionally includes foodie fields in response
ff2c6de feat(backend): add POIService persona routing — foodie → Google Places, others → Overpass
4d4e3d5 feat(backend): add ConfidenceClassifier.classify_place() for Google Places results
159a8f8 feat(backend): add FoodieFilter with meal-time threshold (TDD)
de9a6ca feat(backend): add GooglePlacesClient (Protocol + Fake + Real) and GOOGLE_PLACES_API_KEY config
6e253a1 feat(backend): parse default_trigger_radius_m in PersonaLoader; foodie YAML → google_places
9795d3b feat(backend): add Place model and foodie fields to POI + PersonaConfig
```

Plan D 新增的關鍵 commits（由新到舊）：
```
622c533 chore(opsx): archive plan-d-push-to-talk change (Plan D complete)
3178f93 feat(flutter): show Q&A transcript and response text in NarrationSheet
adfb17b feat(flutter): integrate PushToTalkButton into MapScreen
d440713 feat(flutter): add PushToTalkButton widget with idle/recording/processing/answering states
7631a80 feat(flutter): add QaNotifier with idle/recording/processing/answering state machine (TDD)
2c90d52 feat(flutter): add qaAudioPlayerProvider and micRecorderProvider
c458630 feat(flutter): add BackendClient.qa() with multipart/form-data + QaEvent SSE parsing
24aedd4 feat(flutter): add MicRecorderService with record package for push-to-talk
6dd1ba6 feat(flutter): add duck/unduck to AudioPlayerService for Q&A volume control
af0224f feat(flutter): add QaEvent sealed class
d2fb2e4 feat(backend): wire QAService and /qa router in app factory
bca51a8 feat(backend): add POST /qa SSE endpoint (TDD)
aa4c919 feat(backend): add QAService with STT→LLM→TTS pipeline (TDD)
197c974 feat(backend): add PromptBuilder.build_qa() with poi/no-poi branches
b4c3716 feat(backend): add SttProvider protocol with FakeSttProvider and GeminiSttAdapter
```

---

## 4. Flutter App 架構（Plan F 產出）

```
flutter_app/lib/
├── main.dart                                  ← ProviderScope + runApp(App())
├── app.dart                                   ← ConsumerStatefulWidget + WidgetsBindingObserver + NotificationService.init() [Plan F]
├── features/
│   ├── session/
│   │   ├── persona_data.dart                  ← PersonaInfo model + kPersonas (5 個 persona 常數) [Plan C]
│   │   ├── providers/session_provider.dart    ← SessionNotifier + setPersona/setLang [Plan C 擴充]
│   │   ├── screens/home_screen.dart           ← PersonaSelector + SegmentedButton 語言切換 [Plan C 改版]
│   │   ├── widgets/persona_chip.dart          ← 已棄用（保留檔案但 HomeScreen 不再使用）
│   │   └── widgets/persona_selector.dart      ← 5 張垂直卡片選角 UI [Plan C]
│   ├── map/
│   │   ├── providers/poi_provider.dart        ← PoiNotifier (AsyncNotifier), 250m 重新 fetch
│   │   ├── screens/map_screen.dart            ← GoogleMap + POI markers + NarrationSheet + PushToTalkButton [Plan D]
│   │   └── widgets/poi_marker.dart            ← BitmapDescriptor 依 confidence (azure/yellow/red)
│   ├── narration/
│   │   ├── trigger_engine.dart                ← 純靜態 TriggerEngine.evaluate()
│   │   ├── providers/narration_provider.dart  ← NarrationNotifier, narrate(poi, persona:, lang:) [Plan C 擴充]
│   │   ├── providers/trigger_provider.dart    ← TriggerNotifier, 從 sessionProvider 讀 persona/lang [Plan C]
│   │   ├── widgets/narration_mini_bar.dart    ← 底部 mini bar (playing/paused toggle + skip)
│   │   └── widgets/narration_sheet.dart       ← DraggableScrollableSheet + Q&A 字幕區塊 [Plan D]
│   └── qa/                                    ← [Plan D 新增]
│       ├── providers/qa_provider.dart         ← QaNotifier (idle/recording/processing/answering/error)
│       └── widgets/push_to_talk_button.dart   ← 長按麥克風按鈕 + 視覺狀態動畫
└── shared/
    ├── providers.dart                         ← + notificationServiceProvider / appLifecycleStateProvider [Plan F]
    ├── notification/
    │   └── notification_service.dart          ← abstract NotificationService + Fake + Real (flutter_local_notifications) [Plan F]
    ├── backend/
    │   ├── backend_client.dart                ← + qa() multipart SSE 方法 [Plan D]
    │   ├── sse_parser.dart                    ← 純靜態 SseParser (text/event-stream → SseEvent)
    │   └── models/
    │       ├── poi.dart                       ← POI model (id, name, lat, lon, tags, confidence, distanceM)
    │       ├── narration_event.dart           ← sealed NarrationEvent (Meta/Text/Audio/End/Error)
    │       └── qa_event.dart                  ← sealed QaEvent (Transcript/Text/Audio/End/Error) [Plan D]
    ├── location/
    │   ├── haversine.dart                     ← 純函式 haversine(lat1, lon1, lat2, lon2) → metres
    │   └── location_service.dart              ← abstract LocationService + Real（AndroidSettings/AppleSettings 背景模式）+ Fake [Plan F]
    ├── audio/
    │   └── audio_player_service.dart          ← + duck()/unduck() 方法 [Plan D]
    ├── mic/
    │   └── mic_recorder_service.dart          ← abstract MicRecorderService + Real + Fake [Plan D]
    └── db/
        ├── local_db.dart                      ← Drift schema (sessions + narration_history)
        └── local_db.g.dart                    ← build_runner 產生（勿手動修改）
```

**重要 NarrationEvent 模型細節**（與 backend payload 對齊，勿隨意改動）：
- `EndEvent` — 無任何欄位，`const EndEvent()`
- `TextEvent` — 有 `sentenceIdx` 欄位
- `MetaEvent` — 有 `estimatedDurationS` 欄位
- 全部 subclass 有 `fromJson` factory

**Plan D 新增後端模組：**
- `backend/src/tour_guide/providers/stt.py` — SttProvider Protocol + GeminiSttAdapter + FakeSttProvider
- `backend/src/tour_guide/services/qa_service.py` — QAService（STT→LLM→TTS pipeline）
- `backend/src/tour_guide/api/qa.py` — POST /qa SSE endpoint（multipart form）
- `backend/src/tour_guide/prompts/builder.py` — 新增 `build_qa()` method（含 poi/no-poi 分支）

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

### Step 1：取得真實 API Keys 並填入本地設定（需要人工操作）

```bash
# Android Maps API Key
echo "MAPS_API_KEY_ANDROID=AIza..." >> flutter_app/android/local.properties

# iOS Maps API Key
cp flutter_app/ios/Flutter/LocalConfig.xcconfig.example flutter_app/ios/Flutter/LocalConfig.xcconfig
# 編輯 LocalConfig.xcconfig 填入 MAPS_API_KEY_IOS=AIza...
```

| Key | 取得位置 |
|---|---|
| Gemini API Key | https://aistudio.google.com/apikey |
| Google Maps（Android） | GCP Console → APIs → Maps SDK for Android |
| Google Maps（iOS） | GCP Console → APIs → Maps SDK for iOS |
| Google Places | GCP Console → APIs → Places API |

### Step 2：真機端對端 smoke test

```bash
# 啟動後端（本地）
cd backend && GEMINI_API_KEY=<真實key> .venv/bin/uvicorn tour_guide.main:app --reload

# Flutter Android Emulator
cd flutter_app && flutter run --dart-define-from-file=dart_defines/dev.json

# Flutter iOS Simulator
cd flutter_app && flutter run \
  --dart-define=BACKEND_URL=http://localhost:8000 \
  --dart-define=API_KEY=dev
```

驗證 golden path：
1. HomeScreen 顯示 5 張 persona 卡片，選角 + 切換語言
2. 點「開始旅程」→ 地圖開啟，POI markers 顯示（若 `whileInUse` 權限則顯示 SnackBar）
3. 走近 100m POI → 前景觸發旁白
4. 鎖屏後走近 POI → 顯示本地通知
5. 旁白播放中，長按 PushToTalkButton → Q&A 正常運作

### Step 3：Cloud Run 部署（選做）

```bash
# 建立 GCP 專案（僅需一次）
scripts/setup-gcp.sh

# 部署後端
export GEMINI_API_KEY=...
export GOOGLE_PLACES_API_KEY=...
scripts/deploy-backend.sh

# 設定 Flutter prod dart-define
cp flutter_app/dart_defines/prod.json.example flutter_app/dart_defines/prod.json
# 填入 BACKEND_URL 和 API_KEY
```

---

## 6. 必須知道的 context

### 6.1 Google Maps API Key（Plan F — 使用 local.properties / xcconfig）

Plan F 改用安全注入方式（不進 git）：
- **Android**：`flutter_app/android/local.properties` → `MAPS_API_KEY_ANDROID=AIza...`
- **iOS**：`flutter_app/ios/Flutter/LocalConfig.xcconfig`（從 `.example` 複製）→ `MAPS_API_KEY_IOS=AIza...`

取得 key：Google Cloud Console → Maps SDK for Android + Maps SDK for iOS 啟用

### 6.2 GEMINI_API_KEY（尚未設定）

`backend/.env` 或 `export GEMINI_API_KEY=...`
取得：https://aistudio.google.com/apikey

所有 unit/widget/integration test 均用 fake，不需要真實 key。

### 6.3 Plan F 實作細節（重要）

- `App` widget 已改為 `ConsumerStatefulWidget` + `WidgetsBindingObserver`，`initState` 呼叫 `notificationServiceProvider.init()`，`didChangeAppLifecycleState` 更新 `appLifecycleStateProvider`
- `TriggerNotifier._evaluate()` 讀取 `appLifecycleStateProvider`：`resumed` → `NarrationNotifier.narrate()`，其他 → `NotificationService.showPoiTrigger(poi)`
- `RealLocationService.start()` 依 `Platform.isIOS` 選 `AppleSettings`（`allowBackgroundLocationUpdates: true`）或 `AndroidSettings`（含 `ForegroundNotificationConfig`）
- X-Api-Key：空字串時 middleware 不攔截（開發環境設 `API_KEY=dev`，prod 由 Secret Manager 注入）
- `BackendClient` 的 `apiKey` 從 `const String.fromEnvironment('API_KEY')` 讀取
- dart-define 檔案：`dev.json` 含 `API_KEY=dev`；`prod.json`（gitignored）從 `prod.json.example` 複製後填入
- TriggerNotifier 測試用 `container.listen()` 建立訂閱（`container.read()` 不保持 provider 活躍），再 `await Future.microtask()` 確保事件傳遞

### 6.4 Plan D 實作細節（重要）

- `QaNotifier.stopAndSend()` 有 **500ms guard**：長按不足 500ms 自動靜默取消（不送 /qa）
- `EndQaEvent` sealed class 不能用 `const` constructor（Dart 限制），改為一般 constructor
- `python-multipart` 已加入 `pyproject.toml`（FastAPI Form data 的必要依賴）
- `http_parser` 在 `pubspec.yaml` 顯式宣告（avoid_dynamic_calls lint 要求）
- Q&A 專用獨立 AudioPlayer（`qaAudioPlayerProvider`），旁白（`narrationAudioPlayerProvider`）的別名已在 providers.dart 建立

### 6.5 Plan C 設計限制（MVP 有意為之，後續 Plan 擴充）

- `foodie` persona 的 Google Places POI 路由 → Plan E 範圍（Plan C 先走 osm_wikipedia）
- Flutter UI 文字 i18n（按鈕、對話框）維持中文 → Plan F 範圍
- persona 觸發半徑 per-persona override（foodie 預設 50m）→ Plan F 範圍
- `recordNarration(sessionId: 1, ...)` hardcoded — MVP 不強制 session FK
- `flutter analyze` 僅 info 等級，無 error/warning

### 6.6 Drift build_runner

如果修改 `local_db.dart` schema，需重跑：
```bash
cd flutter_app && dart run build_runner build --delete-conflicting-outputs
```

### 6.7 SubAgent 執行方式

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
| OpenSpec Plan D change（已 archive） | `openspec/changes/archive/2026-05-13-plan-d-push-to-talk/` |
| Plan D 設計規格 | `docs/superpowers/specs/2026-05-13-plan-d-push-to-talk-design.md` |
| Plan D 實作計畫 | `docs/superpowers/plans/2026-05-13-plan-d-push-to-talk.md` |
| OpenSpec Plan F change（已 archive） | `openspec/changes/archive/2026-05-14-plan-f-background-location-deploy/` |
| Plan F 設計規格 | `docs/superpowers/specs/2026-05-14-plan-f-background-location-deploy-design.md` |
| Plan F 實作計畫 | `docs/superpowers/plans/2026-05-14-plan-f-background-location-deploy.md` |
| NotificationService | `flutter_app/lib/shared/notification/notification_service.dart` |
| GCP 設定腳本 | `scripts/setup-gcp.sh` |
| Cloud Run 部署腳本 | `scripts/deploy-backend.sh` |
| 完整設定指引 | `SETUP.md` |
| Prod dart-define 範本 | `flutter_app/dart_defines/prod.json.example` |
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
Plan A（後端）、Plan B（Flutter App）、Plan C（Persona 系統 + 雙語）、Plan D（Push-to-talk Q&A）、Plan E（食家 persona + Google Places）、Plan F（背景定位 + Cloud Run 部署上線）都已完成。
下一步是取得真實 API Keys、填入本地設定，並進行真機端對端 smoke test。
```

—— END HANDOFF
