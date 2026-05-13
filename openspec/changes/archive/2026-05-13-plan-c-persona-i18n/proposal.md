## Why

Plan B MVP 已完成單一靜態 persona（歷史大叔）的旁白功能，後端 `/narration` endpoint 直接 hardcode persona 設定，Flutter HomeScreen 只有一個 `PersonaChip`，無語言選項。Plan C 將 persona 從 1 個擴充為 5 個可選角色，並新增旁白語言切換（zh-TW / en），讓使用者在出發前選定導遊風格與旁白語言，提供更個人化的旅遊體驗。

## What Changes

- 後端新增 4 個 persona YAML 檔（`story_brother`、`gossip_auntie`、`kid_sister`、`foodie`），每個 YAML 包含雙語 system prompt、narration template、voice 設定
- 後端 `PersonaLoader` 新增 `load_all()` classmethod，在 FastAPI startup 預載所有 persona 成 registry dict
- 後端 `/narration` endpoint 改從 registry 取 persona，未知 `persona_id` 回傳 HTTP 400（**原本不驗證 persona，為 BREAKING 行為強化**）
- Flutter 新增 `PersonaInfo` 資料模型與 `kPersonas` 常數（5 個 persona 的展示資訊）
- Flutter 新增 `PersonaSelector` widget（5 張垂直卡片，含 emoji + 中文名 + 描述，可切換選取）
- Flutter `SessionState` 新增 `persona`、`lang` 欄位，`SessionNotifier` 新增 `setPersona()` / `setLang()`（僅 idle 狀態可修改）
- Flutter `NarrationNotifier.narrate()` 改為接收 `persona` / `lang` 具名參數（不再 hardcode）
- Flutter `TriggerNotifier` 觸發旁白前從 `sessionProvider` 讀取當前 persona / lang 後傳入
- Flutter HomeScreen 新增語言切換 `SegmentedButton<String>`（中文 / EN），並以 `PersonaSelector` 取代舊 `PersonaChip`

## Capabilities

### New Capabilities

- `persona-registry`: 後端 5 個 persona YAML 定義 + `PersonaLoader.load_all()` registry 管理；`/narration` endpoint persona 驗證與動態注入
- `persona-selection-ui`: Flutter `PersonaInfo` 常數、`PersonaSelector` 卡片 widget、`SessionState` persona/lang 欄位、`setPersona` / `setLang` 方法

### Modified Capabilities

- `narration-stream`: `NarrationNotifier.narrate()` 簽章新增 `{required String persona, required String lang}` 具名參數，呼叫端需一併更新

## Impact

- 後端：`backend/prompts/personas/`（新增 4 個 YAML）、`backend/src/tour_guide/prompts/loader.py`（新增 `load_all()`）、`backend/src/tour_guide/api/narration.py`（新增 `get_persona_registry` dependency）、`backend/src/tour_guide/main.py`（startup 預載）
- Flutter：新增 `flutter_app/lib/features/session/persona_data.dart`、`flutter_app/lib/features/session/widgets/persona_selector.dart`；修改 `session_provider.dart`、`narration_provider.dart`、`trigger_provider.dart`、`home_screen.dart`
- 測試：後端新增 `test_load_all_personas`、`test_narration_unknown_persona`、`test_narration_all_personas`；Flutter 新增 `persona_selector_test`，更新 `session_provider_test`、`home_screen_test`、`narration_flow_test`、`trigger_provider_test`
- 無新增外部依賴，無影響 Plan A 後端其他 endpoint
