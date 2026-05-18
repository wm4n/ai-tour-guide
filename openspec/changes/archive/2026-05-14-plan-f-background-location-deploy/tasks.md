## 1. Backend — API Key Config + Middleware（TDD）

- [x] 1.1 在 `backend/tests/integration/test_app_factory.py` 新增 4 個 middleware 測試（空 key 放行、正確 key 放行、錯誤 key 返回 401、缺少 header 返回 401）
- [x] 1.2 在 `backend/src/tour_guide/config.py` 新增 `api_key: str = Field("", alias="API_KEY")`
- [x] 1.3 在 `backend/src/tour_guide/main.py` 新增 `@app.middleware("http")` X-Api-Key 驗證邏輯
- [x] 1.4 在 `backend/.env.example` 新增 `API_KEY=` 說明

## 2. Backend — Dockerfile + .dockerignore

- [x] 2.1 新增 `backend/Dockerfile`（FROM python:3.12-slim，安裝依賴，CMD uvicorn 監聽 $PORT）
- [x] 2.2 新增 `backend/.dockerignore`（排除 `__pycache__`、`.pytest_cache`、`.env`、`tests/`、虛擬環境目錄）

## 3. Flutter — flutter_local_notifications dependency

- [x] 3.1 在 `flutter_app/pubspec.yaml` 新增 `flutter_local_notifications: ^17.2.4`

## 4. Flutter — NotificationService（TDD）

- [x] 4.1 新增 `flutter_app/test/unit/notification_service_test.dart`（FakeNotificationService: initCalled、shownPois 記錄測試）
- [x] 4.2 新增 `flutter_app/lib/shared/notification/notification_service.dart`（abstract class + FakeNotificationService + RealNotificationService）

## 5. Flutter — providers.dart 新增 providers

- [x] 5.1 在 `flutter_app/lib/shared/providers.dart` 新增 `notificationServiceProvider`（回傳 `RealNotificationService`）
- [x] 5.2 在 `flutter_app/lib/shared/providers.dart` 新增 `appLifecycleStateProvider`（`StateProvider<AppLifecycleState>`，初始值 `resumed`）

## 6. Flutter — LocationService 新增 checkPermission

- [x] 6.1 在 `flutter_app/lib/shared/location/location_service.dart` abstract class 新增 `checkPermission()` 方法簽名
- [x] 6.2 在 `RealLocationService` 實作 `checkPermission()` 呼叫 `Geolocator.checkPermission()`
- [x] 6.3 在 `FakeLocationService` 實作 `checkPermission()` 回傳 `LocationPermission.whileInUse`
- [x] 6.4 在 `RealLocationService.start()` 依 `Platform.isIOS` 注入 `AppleSettings`（`allowBackgroundLocationUpdates: true`）或 `AndroidSettings`（含 `ForegroundNotificationConfig`）

## 7. Flutter — BackendClient 新增 X-Api-Key header

- [x] 7.1 在 `flutter_app/lib/shared/backend/backend_client.dart` 的 constructor 新增 `apiKey` 參數
- [x] 7.2 在所有 HTTP 請求的 headers 中加入 `X-Api-Key: <apiKey>`

## 8. Flutter — TriggerNotifier 背景路由（TDD）

- [x] 8.1 在 `flutter_app/test/unit/trigger_provider_test.dart` 新增背景狀態下呼叫 `NotificationService.showPoiTrigger` 的測試
- [x] 8.2 在 `flutter_app/lib/features/narration/providers/trigger_provider.dart` 讀取 `appLifecycleStateProvider`
- [x] 8.3 當 `lifecycleState == resumed` 時呼叫 `NarrationNotifier.narrate(poi)`；其他狀態呼叫 `NotificationService.showPoiTrigger(poi)`

## 9. Flutter — HomeScreen whileInUse SnackBar（TDD）

- [x] 9.1 在 `flutter_app/test/widget/home_screen_test.dart` 新增 `whileInUse` 權限時顯示 SnackBar 的測試
- [x] 9.2 在 `flutter_app/lib/features/session/screens/home_screen.dart` 的 `_start()` 中呼叫 `checkPermission()`，若結果為 `whileInUse` 則顯示引導 SnackBar

## 10. Flutter — App widget lifecycle observer

- [x] 10.1 將 `flutter_app/lib/app.dart` 的 `App` widget 改為 `ConsumerStatefulWidget` + `WidgetsBindingObserver`
- [x] 10.2 在 `initState` 中呼叫 `notificationService.init()` 並以 `WidgetsBinding.instance.addObserver(this)` 註冊
- [x] 10.3 實作 `didChangeAppLifecycleState` 更新 `appLifecycleStateProvider`

## 11. Android 平台設定

- [x] 11.1 在 `flutter_app/android/app/src/main/AndroidManifest.xml` 新增 `ACCESS_BACKGROUND_LOCATION`、`FOREGROUND_SERVICE`、`FOREGROUND_SERVICE_LOCATION`、`POST_NOTIFICATIONS` permissions 及 `GeolocatorService` 宣告
- [x] 11.2 在 `flutter_app/android/app/build.gradle.kts` 新增讀取 `local.properties` 的 `MAPS_API_KEY` 注入邏輯（`manifestPlaceholders`）

## 12. iOS 平台設定

- [x] 12.1 在 `flutter_app/ios/Runner/Info.plist` 新增 `UIBackgroundModes: [location]`、三組 `NSLocation*UsageDescription` 及 `MAPS_API_KEY_IOS` 欄位
- [x] 12.2 在 `flutter_app/ios/Runner/AppDelegate.swift` 改從 `Bundle.main.infoDictionary["MAPS_API_KEY_IOS"]` 讀取 Maps API Key（不 hardcode）
- [x] 12.3 在 `flutter_app/ios/Flutter/Debug.xcconfig` 和 `Release.xcconfig` 加入 `#include? "LocalConfig.xcconfig"`
- [x] 12.4 新增 `flutter_app/ios/Flutter/LocalConfig.xcconfig.example` 作為設定範本

## 13. .gitignore 更新 + dart_defines

- [x] 13.1 在 `.gitignore` 新增 `flutter_app/dart_defines/prod.json`、`flutter_app/ios/Flutter/LocalConfig.xcconfig`、`scripts/.env`
- [x] 13.2 在 `flutter_app/dart_defines/dev.json` 新增 `API_KEY` 欄位（空字串）

## 14. Scripts — GCP 設定與部署

- [x] 14.1 新增 `scripts/setup-gcp.sh`（建立 GCP 專案、啟用 API、建立 Secret Manager secret，具備冪等性）
- [x] 14.2 新增 `scripts/deploy-backend.sh`（Cloud Build + Artifact Registry + Cloud Run 部署，輸出服務 URL）

## 15. 文件

- [x] 15.1 新增 `flutter_app/dart_defines/prod.json.example`（含 `BACKEND_URL` 和 `API_KEY` placeholder）
- [x] 15.2 新增根目錄 `SETUP.md`（GCP 設定、iOS/Android API Key 注入、dart_defines 設定、執行指令完整說明）
