## Why

當 app 在模擬器或無 GPS 訊號的裝置上執行時，`positionStreamProvider` 永遠不會發出值，導致地圖相機停在無意義的座標、POI 不會載入、整個導覽體驗完全無法使用。加入語言感知的 GPS fallback，讓開發與測試流程更順暢，並確保在 GPS 訊號不佳時使用者仍能獲得完整體驗。

## What Changes

- **新增** `lib/shared/location/fallback_locations.dart`：語言對應的 fallback 座標常數與 `fallbackPosition(lang)` helper
- **新增** `effectivePositionStreamProvider`（位於 `poi_provider.dart`）：包裝現有 GPS stream，5 秒無 GPS 時注入 fallback 位置
- **新增** `sessionLangProvider` 與 `fallbackTimeoutProvider`：供 `effectivePositionStreamProvider` 讀取當前語言與超時設定（可在測試中 override）
- **更新** `PoiNotifier.build()`：從 `positionStreamProvider` 改為監聽 `effectivePositionStreamProvider`
- **更新** `TriggerNotifier.build()`：從 `positionStreamProvider` 改為監聽 `effectivePositionStreamProvider`
- **更新** `MapScreen`：兩處 `positionStreamProvider` 引用改為 `effectivePositionStreamProvider`；hardcoded fallback `LatLng(25.1023, 121.5482)` 改為 `LatLng(0, 0)`（provider 會在 5 秒內移動相機）

現有 `positionStreamProvider` **保持不變**。

## Capabilities

### New Capabilities
- `default-fallback-location`：語言感知的 GPS fallback 機制——5 秒無 GPS 時自動注入 fallback 位置（zh-TW → 台北故宮博物院，en → Smithsonian），讓地圖與 POI 在無 GPS 環境仍能正常運作

### Modified Capabilities
- `poi-map`：`PoiNotifier` 觸發來源由 `positionStreamProvider` 改為 `effectivePositionStreamProvider`，確保模擬器上也能載入 POI
- `trigger-engine`：`TriggerNotifier` 位置來源由 `positionStreamProvider` 改為 `effectivePositionStreamProvider`

## Impact

- **Flutter 程式碼**：`lib/shared/location/`（新檔）、`lib/features/map/providers/poi_provider.dart`、`lib/features/map/screens/map_screen.dart`、`lib/features/narration/providers/trigger_provider.dart`
- **測試**：新增 `test/unit/fallback_locations_test.dart`、`test/unit/effective_position_provider_test.dart`；更新 `test/unit/poi_provider_test.dart`、`test/unit/trigger_provider_test.dart`（加入 `sessionLangProvider` override）
- **依賴**：無新依賴，複用現有 `geolocator` 與 `fakePosition()` helper
- **破壞性變更**：無——`positionStreamProvider` API 不變，只新增包裝層
