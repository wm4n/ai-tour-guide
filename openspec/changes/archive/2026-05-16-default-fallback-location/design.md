## Context

**當前狀態：**  
app 在模擬器或無 GPS 訊號的裝置上執行時，`positionStreamProvider`（來自 `LocationService.positionStream`）永遠不會發出值。所有依賴位置的元件（`PoiNotifier`、`TriggerNotifier`、`MapScreen`）都靜止不動：地圖相機停在 hardcoded 座標、POI 不載入、導覽體驗完全無法使用。

**技術棧：** Flutter 3.x、Riverpod 2.x、`geolocator` package、Dart `dart:async`

**限制：**
- 不得修改 `positionStreamProvider` 的既有行為（有其他測試依賴它）
- 不得引入新的外部 package 依賴
- fallback 必須是語言感知的，因為 app 同時支援 zh-TW（台灣）與 en（美國）市場

## Goals / Non-Goals

**Goals:**
- GPS 流啟動後 5 秒內未收到任何位置資料時，自動注入語言對應的 fallback 位置
- zh-TW → 台北故宮博物院 (25.1023°N, 121.5484°E)
- en → Smithsonian National Air and Space Museum (38.8882°N, 77.0197°W)
- fallback 後若 GPS 恢復，繼續正常轉發真實位置
- timeout 時間可在測試中 override，確保測試不需等待 5 秒

**Non-Goals:**
- 使用者自訂 fallback 地點
- 持久化 fallback 偏好設定
- 主動偵測模擬器 vs 真實裝置（不需要，timeout 機制即可涵蓋）
- 修改現有 `positionStreamProvider` API

## Decisions

### Decision 1：新增包裝 provider，而非修改現有 provider

**選擇：** 建立 `effectivePositionStreamProvider` 包裝 `positionStreamProvider`，所有 UI 消費者切換到新 provider。

**原因：**
- 單一責任原則：`positionStreamProvider` 只負責 GPS 流，`effectivePositionStreamProvider` 負責回退邏輯
- 不破壞現有測試與程式碼
- 更容易單獨測試回退邏輯

**替代方案：** 直接修改 `positionStreamProvider` 加入 timeout 邏輯 → 違反現有測試期望，且難以在測試中 override timeout

---

### Decision 2：使用 `StreamController.broadcast()` + `dart:async Timer`

**選擇：** 在 `StreamProvider` 內部使用 `StreamController<Position>.broadcast()` 手動管理事件流，搭配 `Timer` 觸發 fallback。

**原因：**
- `StreamController.broadcast()` 允許多個消費者訂閱（map screen、poi notifier、trigger notifier）
- `Timer` 是 Dart 標準庫，不需額外依賴
- `ref.onDispose` 確保 `Timer`、訂閱、`StreamController` 都正確釋放

**替代方案：** 使用 `positionStream.timeout()` Dart 運算子 → 只在流無事件時拋出 `TimeoutException`，不能優雅地注入 fallback 值後繼續轉發

---

### Decision 3：`fallbackTimeoutProvider` 可 override

**選擇：** 將 timeout 時間抽為獨立的 `Provider<Duration>` 預設 5 秒，測試中可 override 為 100ms。

**原因：**
- 測試不需等待 5 秒，可在數百毫秒內完成
- 生產行為不受影響

---

### Decision 4：`sessionLangProvider` 讀取 `sessionProvider`

**選擇：** 新增 `sessionLangProvider` Provider，從 `sessionProvider` 讀取 `lang` 欄位。

**原因：**
- 解耦 `effectivePositionStreamProvider` 對 session 的直接依賴，使測試更容易 override 語言
- 保持 `effectivePositionStreamProvider` 的實作整潔

---

### Decision 5：fallback_locations.dart 複用 `fakePosition()`

**選擇：** 在 `lib/shared/location/fallback_locations.dart` 中呼叫 `location_service.dart` 已有的 `fakePosition()` helper。

**原因：**
- 不重複造輪子：`fakePosition()` 已建構出符合 `geolocator` 要求的 `Position` 物件
- fallback 座標的「構造」與「選擇」邏輯分離，職責清晰

## Risks / Trade-offs

**[Risk] fallback 在低速但有效的 GPS 裝置上仍會觸發** → 5 秒是較寬鬆的閾值，一般裝置 GPS 鎖定通常在 1-3 秒內完成；若仍觸發，使用者會在 fallback 後不久收到真實位置更新，體驗影響極小。

**[Risk] `StreamController.broadcast()` 在 ref dispose 後收到事件** → `ref.onDispose` 中先 `timer.cancel()`、再 `sub.cancel()`、最後 `controller.close()`，關閉順序確保不會發生 `add` after `close`。

**[Risk] 多個 provider 同時 watch `effectivePositionStreamProvider` 造成多個訂閱** → `broadcast()` 天生支援多訂閱者；且 Riverpod 的 provider 快取機制確保同一個 `StreamProvider` 實例只建立一個底層 stream。

**[Trade-off] MapScreen `initialTarget` 改為 `LatLng(0,0)`** → 用戶在頁面載入瞬間可能短暫看到大西洋中部（0,0），但 5 秒內 `effectivePositionStreamProvider` 必然移動相機，影響可接受。

## Migration Plan

1. 建立 `lib/shared/location/fallback_locations.dart`（無依賴）
2. 在 `lib/features/map/providers/poi_provider.dart` 新增三個 provider
3. 更新 `PoiNotifier.build()` 改用 `effectivePositionStreamProvider`
4. 更新 `TriggerNotifier.build()` 改用 `effectivePositionStreamProvider`
5. 更新 `MapScreen` 兩處引用與 `initialTarget`
6. 同步更新受影響的單元測試（加入 `sessionLangProvider` override）

**Rollback：** 若有問題，只需將所有消費者改回 `positionStreamProvider`，並移除新增的三個 provider 與 `fallback_locations.dart` 即可。無資料庫遷移、無 API 變更。

## Open Questions

- 無。設計已完整，所有技術選擇已確定。
