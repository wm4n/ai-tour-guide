## Why

食家（foodie）persona 目前使用 `osm_wikipedia` 作為 POI 來源，僅回傳通用景點資料，無法提供餐廳評分、價位等食家所需的資訊。Plan D 的 Push-to-talk Q&A 已完成，現在需要將食家 persona 切換到 Google Places 真實餐廳資料，讓 AI 旅遊導覽在食家模式下能根據地理位置推薦高評分餐廳。

## What Changes

- **新增** `GooglePlacesClient`（Protocol + Real + Fake 三層架構），根據環境變數 `GOOGLE_PLACES_API_KEY` 切換 Real/Fake 實作
- **新增** `FoodieFilter` 純函式，依用餐時段（11-14、17-21 點）套用不同評分門檻過濾餐廳
- **修改** `POIService` 加入 persona routing：`foodie` → Google Places；其他 persona 維持原有 Overpass pipeline
- **修改** `POI` dataclass（後端 + Flutter）加入 nullable 食家欄位（`rating`、`user_ratings_total`、`price_level`、`place_types`、`vicinity`）
- **修改** `api/poi.py` 條件性輸出 foodie-specific 欄位（非食家 POI 不輸出）
- **修改** `ConfidenceClassifier` 新增 `classify_place()` 食家信心度判定
- **修改** `foodie.yaml`：`poi_source: google_places`、`default_trigger_radius_m: 50`
- **修改** `PersonaConfig` + `PersonaLoader` 支援 `default_trigger_radius_m` 欄位
- **修改** Flutter `PersonaInfo` 加 `defaultTriggerRadiusM`；`kPersonas` 更新（foodie=50m，其他=100m）
- **修改** Flutter `TriggerNotifier` 從 `kPersonas` 讀 per-persona 觸發半徑，取代寫死的 100m
- **新增** Flutter `NarrationSheet._FoodieRatingBar` widget，有 rating 時顯示星評列

## Capabilities

### New Capabilities
- `google-places-client`: Google Places API (New) Nearby Search 的 client 層（Protocol + Real + Fake），含 FoodieFilter 純函式與 persona routing
- `foodie-narration-ui`: Flutter 食家專屬 UI 元件（星評列）與 per-persona 觸發半徑機制

### Modified Capabilities
- `poi-map`: POI 資料結構加入 nullable foodie 欄位（`rating`、`price_level` 等）；API 回應格式條件性包含食家欄位
- `trigger-engine`: `TriggerNotifier` 改為從 persona 設定讀取觸發半徑，不再寫死 100m
- `tour-session`: `PersonaInfo` 加 `defaultTriggerRadiusM`；`foodie` persona 設定從 osm_wikipedia 改為 google_places

## Impact

- **後端新增**：`backend/src/tour_guide/clients/google_places.py`、`backend/src/tour_guide/services/foodie_filter.py`
- **後端修改**：`models/poi.py`、`models/persona.py`、`prompts/loader.py`、`services/confidence.py`、`services/poi_service.py`、`api/poi.py`、`config.py`、`main.py`
- **YAML 修改**：`backend/prompts/personas/foodie.yaml`
- **Flutter 修改**：`shared/backend/models/poi.dart`、`features/session/persona_data.dart`、`features/narration/providers/trigger_provider.dart`、`features/narration/widgets/narration_sheet.dart`
- **外部相依**：新增 `GOOGLE_PLACES_API_KEY` 環境變數（可選；空值時使用 Fake client）
- **不影響**：其他 4 個 persona 的 narration 邏輯、Q&A pipeline、TTS/STT、部署設定
