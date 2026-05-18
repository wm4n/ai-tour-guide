## Why

App 目前僅在前景運作，使用者鎖屏後無法收到景點觸發通知，且後端仍跑在本機無法給真機使用；Plan F 補上「背景定位 → 本地通知」能力並將後端容器化部署至 Cloud Run，讓 App 達到可公開展示的完整程度。

## What Changes

- **後端** 新增 `X-Api-Key` header 驗證 middleware，`API_KEY` 為空時開發模式自動放行
- **後端** 新增 `Dockerfile` + `.dockerignore`，支援 `gcloud builds submit` 直接建置
- **Flutter** 新增 `flutter_local_notifications` dependency
- **Flutter** 新增 `NotificationService`（abstract + `FakeNotificationService` + `RealNotificationService`）
- **Flutter** `providers.dart` 新增 `notificationServiceProvider` + `appLifecycleStateProvider`
- **Flutter** `LocationService` 新增 `checkPermission()`，`RealLocationService.start()` 依平台注入 `AndroidSettings`（含 `ForegroundNotificationConfig`）或 `AppleSettings`（`allowBackgroundLocationUpdates: true`）
- **Flutter** `BackendClient` constructor 新增 `apiKey` 參數，所有請求自動附帶 `X-Api-Key` header
- **Flutter** `TriggerNotifier` 依 `appLifecycleStateProvider` 判斷前景（旁白）／背景（本地通知）路由
- **Flutter** `HomeScreen._start()` 新增 `checkPermission()` 判斷，`whileInUse` 時顯示引導 SnackBar
- **Flutter** `App` widget 改為 `ConsumerStatefulWidget` + `WidgetsBindingObserver`，同步 lifecycle state 並呼叫 `NotificationService.init()`
- **Android** `AndroidManifest.xml` 新增背景定位、前景服務、通知三組 permissions + `GeolocatorService` 宣告
- **Android** `build.gradle.kts` 讀取 `local.properties` 注入 `MAPS_API_KEY`
- **iOS** `Info.plist` 新增 `UIBackgroundModes: location`、三組 `NSLocation*UsageDescription`、`MAPS_API_KEY_IOS`
- **iOS** `AppDelegate.swift` 改從 Bundle 讀取 Maps API Key（不 hardcode）
- **iOS** `Debug.xcconfig` / `Release.xcconfig` 加入 `#include? "LocalConfig.xcconfig"`
- **Scripts** 新增 `setup-gcp.sh`（建立專案/啟用 API/建 Secret）和 `deploy-backend.sh`（build + deploy）
- **Docs** 新增 `dart_defines/prod.json.example` + 根目錄 `SETUP.md`
- **gitignore** 補充 `dart_defines/prod.json`、`ios/Flutter/LocalConfig.xcconfig`、`scripts/.env`

## Capabilities

### New Capabilities

- `background-location`: App 鎖屏時持續收 GPS（geolocator 背景模式），TriggerNotifier 在背景狀態觸發本地通知而非旁白
- `local-notification`: flutter_local_notifications 封裝（NotificationService abstract + Fake + Real），顯示景點到達推播
- `backend-api-key-auth`: X-Api-Key header 驗證 middleware，`API_KEY` 環境變數為空時開發模式放行
- `cloud-run-deploy`: Dockerfile 容器化後端 + gcloud scripts 部署到 Cloud Run asia-east1
- `maps-api-key-injection`: Android local.properties + iOS xcconfig 安全注入 Google Maps API Key，不進 git

### Modified Capabilities

- `trigger-engine`: TriggerNotifier 新增前景/背景路由邏輯（appLifecycleStateProvider），背景時改呼叫 NotificationService 而非 NarrationNotifier
- `tour-session`: HomeScreen._start() 新增 checkPermission() 引導，AppLifecycleState 由 App widget 統一管理
- `poi-map`: BackendClient 新增 apiKey 參數，所有 API 請求附帶 X-Api-Key header

## Impact

**程式碼：**
- `backend/src/tour_guide/config.py` — 新增 `api_key` 欄位
- `backend/src/tour_guide/main.py` — 新增 middleware
- `backend/Dockerfile` + `backend/.dockerignore`（新建）
- `flutter_app/pubspec.yaml` — 新增 `flutter_local_notifications: ^17.2.4`
- `flutter_app/lib/shared/notification/notification_service.dart`（新建）
- `flutter_app/lib/shared/providers.dart` — 新增兩個 provider
- `flutter_app/lib/shared/location/location_service.dart` — 新增 checkPermission + 背景 LocationSettings
- `flutter_app/lib/shared/backend/backend_client.dart` — 新增 apiKey
- `flutter_app/lib/features/narration/providers/trigger_provider.dart` — 背景路由
- `flutter_app/lib/features/session/screens/home_screen.dart` — SnackBar 引導
- `flutter_app/lib/app.dart` — lifecycle observer
- Android/iOS 平台設定檔
- `scripts/setup-gcp.sh` + `scripts/deploy-backend.sh`（新建）

**測試衝擊：**
- 後端：195 → 199+ tests（新增 4 個 middleware 測試）
- Flutter：77 → 79+ tests（新增 NotificationService 3 + HomeScreen 1 + TriggerNotifier 1）

**依賴新增：**
- `flutter_local_notifications: ^17.2.4`

**外部服務：**
- GCP Project + Cloud Run + Artifact Registry + Secret Manager（asia-east1）
- Google Maps SDK（Android + iOS）、Google Places API、Gemini API
