## 1. fallback_locations.dart（新增）

- [x] 1.1 建立 `test/unit/fallback_locations_test.dart`，包含 zh-TW、en、unknown lang 三個測試案例（Red）
- [x] 1.2 執行測試確認失敗（`flutter test test/unit/fallback_locations_test.dart`）
- [x] 1.3 建立 `lib/shared/location/fallback_locations.dart`，實作 `fallbackPosition(String lang)` 複用 `fakePosition()`
- [x] 1.4 執行測試確認全數通過（Green）

## 2. effectivePositionStreamProvider（新增 providers）

- [x] 2.1 建立 `test/unit/effective_position_provider_test.dart`，包含 4 個測試：GPS 先到、zh-TW timeout、en timeout、fallback 後 GPS 恢復（Red）
- [x] 2.2 執行測試確認失敗
- [x] 2.3 在 `lib/features/map/providers/poi_provider.dart` 新增 `sessionLangProvider`（讀取 `sessionProvider.lang`）
- [x] 2.4 在同檔新增 `fallbackTimeoutProvider`（預設 `Duration(seconds: 5)`）
- [x] 2.5 在同檔新增 `effectivePositionStreamProvider`（StreamController.broadcast + Timer fallback 邏輯，含 `ref.onDispose` 清理）
- [x] 2.6 執行測試確認全數通過（Green）

## 3. PoiNotifier 切換至 effectivePositionStreamProvider

- [x] 3.1 在 `test/unit/poi_provider_test.dart` 的 `ProviderContainer` 加入 `sessionLangProvider.overrideWithValue('zh-TW')`（Red）
- [x] 3.2 更新 `PoiNotifier.build()` 中的 `ref.listen` 改用 `effectivePositionStreamProvider`
- [x] 3.3 執行測試確認通過（`flutter test test/unit/poi_provider_test.dart`）

## 4. TriggerNotifier 切換至 effectivePositionStreamProvider

- [x] 4.1 在 `test/unit/trigger_provider_test.dart` 的兩個 `ProviderContainer` 均加入 `sessionLangProvider.overrideWithValue('zh-TW')`（Red）
- [x] 4.2 更新 `TriggerNotifier.build()` 中的 `ref.watch` 改用 `effectivePositionStreamProvider`
- [x] 4.3 執行測試確認通過（`flutter test test/unit/trigger_provider_test.dart`）

## 5. MapScreen 切換至 effectivePositionStreamProvider

- [x] 5.1 將 `map_screen.dart` 中兩處 `positionStreamProvider` 引用改為 `effectivePositionStreamProvider`
- [x] 5.2 將 `initialTarget` 的 hardcoded `LatLng(25.1023, 121.5482)` 改為 `LatLng(0, 0)`

## 6. 驗證與收尾

- [ ] 6.1 執行完整單元測試（`cd flutter_app && flutter test test/unit/`）確認全數通過
- [ ] 6.2 執行 `flutter analyze --no-fatal-infos` 確認無分析錯誤
- [ ] 6.3 在模擬器上啟動 app，確認 5 秒內地圖相機移至故宮（zh-TW）且 POI 正常載入
