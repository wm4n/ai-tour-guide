## 1. Backend — PersonaLoader.load_all()

- [x] 1.1 在 `backend/tests/unit/test_persona_loader.py` 新增 `TestPersonaLoaderLoadAll` class（含 4 個測試：load_all 含 history_uncle、keyed_by_id、空目錄、自訂目錄 with YAML）
- [x] 1.2 執行 `TestPersonaLoaderLoadAll` 確認失敗（AttributeError: no attribute 'load_all'）
- [x] 1.3 在 `backend/src/tour_guide/prompts/loader.py` 的 `PersonaLoader` class 末尾加入 `load_all(base_dir)` classmethod
- [x] 1.4 執行所有 `test_persona_loader.py` 測試確認全部通過
- [x] 1.5 Commit: `feat(backend): add PersonaLoader.load_all() to load all persona YAMLs`

## 2. Backend — 4 個新 Persona YAML 檔

- [x] 2.1 在 `test_persona_loader.py` 新增 `TestAllPersonaYamls` class（parametrize 5 個 persona_id，smoke test system_prompt + narration_template 含 zh-TW + en）
- [x] 2.2 建立 `backend/prompts/personas/story_brother.yaml`，確認 smoke test 通過
- [x] 2.3 建立 `backend/prompts/personas/gossip_auntie.yaml`，確認 smoke test 通過
- [x] 2.4 建立 `backend/prompts/personas/kid_sister.yaml`，確認 smoke test 通過
- [x] 2.5 建立 `backend/prompts/personas/foodie.yaml`，確認 smoke test 通過（所有 5 個 YAML smoke tests 全綠）
- [x] 2.6 Commit: `feat(backend): add story_brother, gossip_auntie, kid_sister, foodie persona YAMLs`

## 3. Backend — 接入 PersonaRegistry + endpoint 驗證

- [x] 3.1 在 `test_narration_api.py` 新增 `test_unknown_persona_returns_400` 測試，並加入 `_FAKE_REGISTRY` + 更新 `app` fixture 以 override `get_persona_registry`
- [x] 3.2 執行新測試確認失敗（ImportError: cannot import name 'get_persona_registry'）
- [x] 3.3 修改 `backend/src/tour_guide/api/narration.py`：新增 `get_persona_registry()` dependency function，endpoint 從 registry 取 persona，未知 persona_id → HTTP 400
- [x] 3.4 修改 `backend/src/tour_guide/main.py`：import `PersonaLoader`，在 `create_app()` 呼叫 `PersonaLoader.load_all()` 並 override `narration.get_persona_registry`
- [x] 3.5 執行 `cd backend && .venv/bin/pytest -v` 確認所有後端測試通過
- [x] 3.6 Commit: `feat(backend): wire PersonaLoader into /narration endpoint, unknown persona → 400`

## 4. Flutter — PersonaData 常數

- [x] 4.1 建立 `flutter_app/lib/features/session/persona_data.dart`（`PersonaInfo` class + `kPersonas` 5 個常數）
- [x] 4.2 執行 `flutter analyze lib/features/session/persona_data.dart` 確認無 error
- [x] 4.3 Commit: `feat(flutter): add PersonaInfo model and kPersonas constants`

## 5. Flutter — SessionState persona/lang + setPersona/setLang

- [x] 5.1 在 `flutter_app/test/unit/session_provider_test.dart` 新增 5 個測試（setPersona idle/active、setLang idle/active、default lang）
- [x] 5.2 執行 `flutter test test/unit/session_provider_test.dart` 確認失敗
- [x] 5.3 修改 `flutter_app/lib/features/session/providers/session_provider.dart`：`SessionState` 新增 `persona`/`lang` 欄位與 `copyWith()`，`SessionNotifier` 新增 `setPersona()`/`setLang()`，`start()` 傳入 `state.persona`/`state.lang`
- [x] 5.4 執行 `flutter test test/unit/session_provider_test.dart` 確認全部通過
- [x] 5.5 Commit: `feat(flutter): expose persona/lang in SessionState.copyWith, add setPersona/setLang`

## 6. Flutter — PersonaSelector widget

- [x] 6.1 建立 `flutter_app/test/widget/persona_selector_test.dart`（4 個測試：顯示 5 個名字、預設 check_circle、tap 切換選取、顯示 emoji）
- [x] 6.2 執行 `flutter test test/widget/persona_selector_test.dart` 確認失敗（找不到 PersonaSelector）
- [x] 6.3 建立 `flutter_app/lib/features/session/widgets/persona_selector.dart`（ConsumerWidget，5 張垂直卡片，選取卡片顯示藍色 border + check_circle icon）
- [x] 6.4 執行 `flutter test test/widget/persona_selector_test.dart` 確認全部通過
- [x] 6.5 Commit: `feat(flutter): add PersonaSelector vertical card widget with selection state`

## 7. Flutter — NarrationNotifier.narrate() 接收 persona/lang 參數

- [x] 7.1 在 `flutter_app/test/integration/narration_flow_test.dart` 將所有 `narrate(_testPoi)` 呼叫改為 `narrate(_testPoi, persona: 'history_uncle', lang: 'zh-TW')`
- [x] 7.2 執行 `flutter test test/integration/narration_flow_test.dart` 確認失敗（named param not defined）
- [x] 7.3 修改 `flutter_app/lib/features/narration/providers/narration_provider.dart`：`narrate()` 簽章改為 `narrate(POI poi, {required String persona, required String lang})`，移除 hardcode，將 persona/lang 傳給 `_client.narrate()` 及 `_recordNarration()`
- [x] 7.4 執行 `flutter test test/integration/narration_flow_test.dart` 確認全部通過
- [x] 7.5 Commit: `feat(flutter): narrate() accepts persona/lang params, reads from session state`

## 8. Flutter — TriggerNotifier 讀取 session 後傳遞 persona/lang

- [x] 8.1 確認現有 `flutter test test/unit/trigger_provider_test.dart` 通過（建立基線）
- [x] 8.2 修改 `flutter_app/lib/features/narration/providers/trigger_provider.dart`：import `session_provider`，在觸發旁白前 `ref.read(sessionProvider)` 取得 persona/lang，傳入 `narrate(poi, persona:..., lang:...)`
- [x] 8.3 執行 `flutter test test/unit/trigger_provider_test.dart` 確認通過
- [x] 8.4 Commit: `feat(flutter): TriggerNotifier reads persona/lang from sessionProvider before narrating`

## 9. Flutter — HomeScreen 改版

- [x] 9.1 完整替換 `flutter_app/test/widget/home_screen_test.dart`（4 個測試：顯示開始旅程按鈕、顯示 5 張 persona 卡片、顯示語言 SegmentedButton、history_uncle 預設選取）
- [x] 9.2 執行 `flutter test test/widget/home_screen_test.dart` 確認失敗
- [x] 9.3 修改 `flutter_app/lib/features/session/screens/home_screen.dart`：改為 `SingleChildScrollView` 包覆，標題下方加入語言 `SegmentedButton<String>`（中文/EN），加入 `PersonaSelector`，移除舊 `PersonaChip`
- [x] 9.4 執行 `flutter test test/widget/home_screen_test.dart` 確認全部通過
- [x] 9.5 Commit: `feat(flutter): restructure HomeScreen with PersonaSelector cards and language toggle`

## 10. 最終驗收

- [x] 10.1 執行 `cd backend && .venv/bin/pytest -v` 確認所有後端測試通過，`ruff check src/` 無 error
- [x] 10.2 執行 `cd flutter_app && flutter test` 確認所有測試通過
- [x] 10.3 執行 `cd flutter_app && flutter analyze` 確認無 error
- [ ] 10.4 手動測試：Flutter App 顯示 5 張 persona 卡片，點選切換，語言切換，開始旅程進入地圖
