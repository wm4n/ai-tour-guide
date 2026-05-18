## 1. 後端模型擴充

- [x] 1.1 在 `backend/tests/unit/test_poi_models.py` 新增 `TestPlaceModel` 測試（寫失敗測試）
- [x] 1.2 在 `backend/src/tour_guide/models/poi.py` 新增 `Place` dataclass，並在 `POI` dataclass 加入 nullable foodie 欄位（`rating`, `user_ratings_total`, `price_level`, `place_types`, `vicinity`）
- [x] 1.3 在 `backend/src/tour_guide/models/persona.py` 的 `PersonaConfig` dataclass 末尾加入 `default_trigger_radius_m: int = 100`
- [x] 1.4 執行 `pytest tests/unit/test_poi_models.py -v` 確認全部通過

## 2. 後端 PersonaLoader + foodie.yaml

- [x] 2.1 在 `backend/tests/unit/test_persona_loader.py` 新增 `TestPersonaLoaderDefaultTriggerRadius` 測試 class（寫失敗測試）
- [x] 2.2 更新 `backend/src/tour_guide/prompts/loader.py` 的 `_parse()` 加入解析 `default_trigger_radius_m`（預設 100）
- [x] 2.3 更新 `backend/prompts/personas/foodie.yaml`：將 `poi_source` 改為 `google_places`，新增 `default_trigger_radius_m: 50`
- [x] 2.4 執行 `pytest tests/unit/test_persona_loader.py -v` 確認全部通過

## 3. 後端 AppConfig + GooglePlacesClient

- [x] 3.1 在 `backend/src/tour_guide/config.py` 加入 `google_places_api_key: str = Field("", alias="GOOGLE_PLACES_API_KEY")`
- [x] 3.2 建立 `backend/tests/unit/test_google_places_client.py`（FakeGooglePlacesClient 測試，寫失敗測試）
- [x] 3.3 建立 `backend/src/tour_guide/clients/google_places.py`，包含：`GooglePlacesClient` Protocol、`FakeGooglePlacesClient`、`RealGooglePlacesClient`（含指數退避）、`_parse_place()` helper
- [x] 3.4 確認 `backend/src/tour_guide/clients/__init__.py` 存在（若無則建立空檔）
- [x] 3.5 執行 `pytest tests/unit/test_google_places_client.py -v` 確認全部通過

## 4. 後端 FoodieFilter（TDD）

- [x] 4.1 建立 `backend/tests/unit/test_foodie_filter.py`，包含 `TestFoodieFilterNormalHours`、`TestFoodieFilterMealHours`、`TestFoodieFilterNoneValues`、`TestFoodieFilterMixed`（寫失敗測試）
- [x] 4.2 建立 `backend/src/tour_guide/services/foodie_filter.py`，實作 `filter_places(places, current_hour)` 純函式，含用餐時段門檻邏輯
- [x] 4.3 執行 `pytest tests/unit/test_foodie_filter.py -v` 確認全部通過

## 5. 後端 ConfidenceClassifier 食家分支（TDD）

- [x] 5.1 在 `backend/tests/unit/test_confidence.py` 加入 `TestConfidenceClassifierPlace` 測試 class（寫失敗測試）
- [x] 5.2 更新 `backend/src/tour_guide/services/confidence.py`，加入 `classify_place(place: Place) -> str` static method
- [x] 5.3 執行 `pytest tests/unit/test_confidence.py -v` 確認全部通過

## 6. 後端 POIService persona routing（TDD）

- [x] 6.1 在 `backend/tests/integration/test_poi_service.py` 加入 `TestPOIServiceFoodieRouting` 測試 class（寫失敗測試）
- [x] 6.2 完整替換 `backend/src/tour_guide/services/poi_service.py`，加入：`google_places` 可選參數、`_place_to_poi()` helper、`_nearby_foodie()` 方法、`nearby()` persona routing 邏輯（`foodie` → Google Places，其他 → Overpass）
- [x] 6.3 執行 `pytest tests/integration/test_poi_service.py -v` 確認全部通過（含原有測試）

## 7. 後端 api/poi.py 輸出 foodie 欄位 + integration test

- [x] 7.1 在 `backend/tests/integration/test_poi_api.py` 加入 `sample_foodie_poi` fixture 及 foodie/non-foodie 回應格式測試（寫失敗測試）
- [x] 7.2 完整替換 `backend/src/tour_guide/api/poi.py`，加入 `_serialize_poi()` 函式，條件性輸出 foodie 欄位（`if p.rating is not None`）
- [x] 7.3 執行 `pytest tests/integration/test_poi_api.py -v` 確認全部通過

## 8. 後端 main.py wiring + 全套測試

- [x] 8.1 完整替換 `backend/src/tour_guide/main.py`，加入 `RealGooglePlacesClient`/`FakeGooglePlacesClient` import 及 wiring 邏輯
- [x] 8.2 執行 `pytest -v` 確認全套後端測試通過
- [x] 8.3 執行 `ruff check src/` 確認無 lint error（新增檔案全部通過，既有 6 個 issue 屬舊有問題）

## 9. Flutter POI model 擴充（TDD）

- [x] 9.1 在 `flutter_app/test/unit/models_test.dart` 的 `group('POI.fromJson', ...)` 加入 foodie 欄位解析測試和非食家 null 欄位測試（寫失敗測試）
- [x] 9.2 完整替換 `flutter_app/lib/shared/backend/models/poi.dart`，加入 nullable foodie 欄位及 `fromJson` 解析邏輯
- [x] 9.3 執行 `flutter test test/unit/models_test.dart` 確認通過
- [x] 9.4 執行 `flutter test` 確認全套 Flutter 測試通過

## 10. Flutter PersonaInfo + kPersonas 觸發半徑

- [x] 10.1 在 `flutter_app/test/unit/trigger_engine_test.dart` 加入自訂 radiusM 50m 的兩個測試案例
- [x] 10.2 完整替換 `flutter_app/lib/features/session/persona_data.dart`，在 `PersonaInfo` 加入 `defaultTriggerRadiusM: int` 欄位，更新 `kPersonas`（foodie=50，其他=100）
- [x] 10.3 執行 `flutter test test/unit/trigger_engine_test.dart` 確認通過
- [x] 10.4 執行 `flutter test` 確認全套 Flutter 測試通過

## 11. Flutter TriggerNotifier 讀 persona 觸發半徑

- [x] 11.1 完整替換 `flutter_app/lib/features/narration/providers/trigger_provider.dart`，從 `kPersonas` 讀取 `defaultTriggerRadiusM` 並傳入 `TriggerEngine.evaluate()`
- [x] 11.2 執行 `flutter test` 確認全套測試通過
- [x] 11.3 執行 `flutter analyze` 確認無 error/warning（僅有 info 等級）

## 12. Flutter NarrationSheet _FoodieRatingBar（widget test）

- [x] 12.1 在 `flutter_app/test/widget/narration_sheet_test.dart` 加入 foodie 星評列顯示和非食家隱藏的兩個 widget 測試（寫失敗測試）
- [x] 12.2 在 `flutter_app/lib/features/narration/widgets/narration_sheet.dart` 加入 `_FoodieRatingBar` private widget，並在 `NarrationSheet.build()` 適當位置引用
- [x] 12.3 確認 `narration_sheet.dart` 頂部 import 包含 `package:flutter_app/shared/backend/models/poi.dart`
- [x] 12.4 執行 `flutter test test/widget/narration_sheet_test.dart` 確認通過
- [x] 12.5 執行 `flutter test` 確認全套測試通過
- [x] 12.6 執行 `flutter analyze` 確認無 error/warning（僅有 info 等級）

## 13. 最終驗收

- [x] 13.1 執行 `cd backend && .venv/bin/pytest -v` 確認全套後端測試通過（195 passed, 2 skipped）
- [x] 13.2 執行 `cd backend && .venv/bin/ruff check src/` 確認無 lint error（新增檔案全部通過）
- [x] 13.3 執行 `cd flutter_app && flutter test` 確認全套 Flutter 測試通過（77 passed）
- [x] 13.4 執行 `cd flutter_app && flutter analyze` 確認無 error/warning（12 個 info 等級）
- [x] 13.5 手動驗證：FoodieFilter 一般時段和用餐時段過濾行為正確
- [x] 13.6 更新 `tasks/session-handoff.md`，將 Plan E 狀態標記為完成
