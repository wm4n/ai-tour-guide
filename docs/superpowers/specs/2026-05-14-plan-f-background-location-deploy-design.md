# Plan F — 背景定位 + 部署上線 設計文件

| 欄位 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 撰寫日期 | 2026-05-14 |
| 適用範圍 | Plan F（背景定位 + Cloud Run 部署上線） |
| 前置條件 | Plan A–E 全部完成（Flutter 77/77 tests pass，後端 195/195 pass） |

---

## 1. 目標

| 子目標 | 說明 |
|---|---|
| 背景定位 | App 鎖屏時持續收 GPS，進入景點範圍自動顯示本地通知 |
| Cloud Run 部署 | 後端容器化並部署到 `asia-east1`，提供穩定公開 URL |
| API Key 設定 | Google Maps、Google Places、Gemini、X-Api-Key 全部注入，不進 git |
| 雙平台支援 | iOS 與 Android 同步進行，各自完成真機驗收 |

---

## 2. 背景定位設計

### 2.1 策略選擇

採用「**前景為主 + 背景通知**」策略（Option C）：

- **前景 / 鎖屏（App 在記憶體）**：`geolocator` 背景模式持續收 GPS，`TriggerNotifier` 觸發時顯示本地通知
- **App 被系統 kill**：不偵測位置（v1 接受此限制），UI 引導使用者保持 App 開啟

選用 `geolocator`（現有套件）+ `flutter_local_notifications`（新增），不引入第三方商業 plugin。

### 2.2 平台權限設定

#### Android（`flutter_app/android/app/src/main/AndroidManifest.xml`）

新增以下 permissions（在現有 FINE/COARSE location 之後）：

```xml
<uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION"/>
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
```

在 `<application>` 內新增 Foreground Service：

```xml
<service
    android:name="com.baseflow.geolocator.GeolocatorService"
    android:foregroundServiceType="location"
    android:exported="false"/>
```

#### iOS（`flutter_app/ios/Runner/Info.plist`）

新增：

```xml
<key>UIBackgroundModes</key>
<array>
    <string>location</string>
</array>
<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>AI Tour Guide 需要在背景持續偵測位置，以便在你走近景點時自動播報旁白。</string>
<key>NSLocationAlwaysUsageDescription</key>
<string>AI Tour Guide 需要一律允許定位，才能在鎖屏時繼續導覽。</string>
```

### 2.3 LocationService 升級

`RealLocationService.start()` 改為依平台注入對應的 `LocationSettings`：

```dart
void start() {
  _controller = StreamController<Position>.broadcast();
  final settings = Platform.isIOS
      ? AppleSettings(
          accuracy: LocationAccuracy.high,
          distanceFilter: 10,
          allowBackgroundLocationUpdates: true,
          pauseLocationUpdatesAutomatically: false,
        )
      : AndroidSettings(
          accuracy: LocationAccuracy.high,
          distanceFilter: 10,
          foregroundNotificationConfig: const ForegroundNotificationConfig(
            notificationTitle: 'AI Tour Guide',
            notificationText: '正在偵測附近景點...',
            enableWakeLock: true,
          ),
        );
  _subscription = Geolocator.getPositionStream(
    locationSettings: settings,
  ).listen(_controller!.add, onError: _controller!.addError);
}
```

介面（`LocationService` abstract class）不變，`FakeLocationService` 不受影響。

### 2.4 NotificationService（新增）

路徑：`flutter_app/lib/shared/notification/notification_service.dart`

```dart
abstract class NotificationService {
  Future<void> init();
  Future<void> showPoiTrigger(Poi poi);
  Stream<String?> get onNotificationTap; // 回傳 poi.id
}
```

**RealNotificationService：**
- `init()`：初始化 `flutter_local_notifications`，Android 建立 `high_importance_channel`，iOS 請求通知權限
- `showPoiTrigger(poi)`：顯示通知「🗺 你附近有景點：{poi.name}，點擊開啟旁白」
- `onNotificationTap`：使用者點通知後，`GoRouter` 導向 `/map` 並透過 `TriggerNotifier` 觸發旁白

**FakeNotificationService：**（用於測試，記錄呼叫但不顯示真實通知）

### 2.5 TriggerNotifier 整合

在 `TriggerNotifier._onTrigger(poi)` 內：

```
App 狀態判斷（AppLifecycleState）：
├─ resumed（前景）→ 現有旁白流程（NarrationNotifier.narrate）
└─ paused / detached（背景）→ NotificationService.showPoiTrigger(poi)
```

### 2.6 權限提示 UI

`HomeScreen` 按「開始旅程」時：

1. `requestPermission()` 若回傳 `whileInUse`（而非 `always`）→ 顯示 persona 口吻的 dialog
2. Dialog 提供「前往設定」按鈕 → `Geolocator.openAppSettings()`
3. 僅 `always` 才進入 `/map`（`whileInUse` 也放行但顯示警告 banner）

---

## 3. 後端容器化設計

### 3.1 Dockerfile

路徑：`backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY prompts/ prompts/

ENV PROMPTS_DIR=/app/prompts
ENV PORT=8080

CMD ["uvicorn", "tour_guide.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 3.2 .dockerignore

路徑：`backend/.dockerignore`

```
.venv/
__pycache__/
*.pyc
tests/
.env
.env.*
```

### 3.3 config.py 補充

新增 `PROMPTS_DIR` 從環境變數讀取（已有 `POI_CACHE_DIR` / `NARRATION_CACHE_DIR` 模式，照同樣做法）。

---

## 4. GCP 設定與部署

### 4.1 setup-gcp.sh

路徑：`scripts/setup-gcp.sh`

執行步驟：

1. 建立新 GCP 專案（`ai-tour-guide-XXXXX`，隨機 suffix 避免衝突）
2. 設定為預設專案（`gcloud config set project`）
3. **提示使用者**前往 Console 綁定 Billing Account（無法用 CLI 自動化）
4. 啟用所需 API：
   - `run.googleapis.com`
   - `artifactregistry.googleapis.com`
   - `cloudbuild.googleapis.com`
   - `secretmanager.googleapis.com`
   - `maps-android-backend.googleapis.com`
   - `maps-ios-backend.googleapis.com`
   - `places.googleapis.com`
5. 建立 Artifact Registry repo（`docker` format，`asia-east1`）
6. 建立 Secret Manager secret `tour-guide-api-key`（提示使用者輸入值）
7. 建立 Cloud Run Service Account + 最小 IAM 綁定
8. 輸出 `PROJECT_ID`、`IMAGE_URL`、`SERVICE_URL_PLACEHOLDER` 供後續使用

### 4.2 deploy-backend.sh

路徑：`scripts/deploy-backend.sh`

```bash
#!/bin/bash
set -euo pipefail

IMAGE_URL="asia-east1-docker.pkg.dev/$PROJECT_ID/tour-guide/backend:latest"

gcloud builds submit ../backend --tag "$IMAGE_URL"

gcloud run deploy ai-tour-guide-backend \
  --image "$IMAGE_URL" \
  --region asia-east1 \
  --platform managed \
  --set-env-vars "GEMINI_API_KEY=$GEMINI_API_KEY,GOOGLE_PLACES_API_KEY=$GOOGLE_PLACES_API_KEY" \
  --set-secrets "API_KEY=tour-guide-api-key:latest" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3

echo "✅ 部署完成"
gcloud run services describe ai-tour-guide-backend \
  --region asia-east1 \
  --format "value(status.url)"
```

### 4.3 X-Api-Key 驗證（後端）

在 `backend/src/tour_guide/main.py` 加入 FastAPI middleware：

```python
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    key = request.headers.get("X-Api-Key")
    if key != settings.api_key:
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    return await call_next(request)
```

`settings.api_key` 從環境變數 `API_KEY` 讀取（Secret Manager 掛載）。開發環境設 `API_KEY=dev` 即可。

---

## 5. API Key 設定與注入

### 5.1 Google Maps API Key

**Android：**

`flutter_app/android/local.properties`（不進 git，已在 .gitignore）：
```properties
MAPS_API_KEY_ANDROID=AIza...
```

`flutter_app/android/app/build.gradle` 讀取並注入：
```groovy
def localProperties = new Properties()
localProperties.load(new FileInputStream(rootProject.file('local.properties')))

android {
    defaultConfig {
        manifestPlaceholders['MAPS_API_KEY'] = localProperties['MAPS_API_KEY_ANDROID'] ?: ''
    }
}
```

`AndroidManifest.xml` 改用 `${MAPS_API_KEY}`。

**iOS：**

`flutter_app/ios/Flutter/Debug.xcconfig` 與 `Release.xcconfig` 各加一行：
```
MAPS_API_KEY_IOS=AIza...
```

`AppDelegate.swift` 改從 Bundle 讀取：
```swift
let key = Bundle.main.object(forInfoDictionaryKey: "MAPS_API_KEY_IOS") as? String ?? ""
GMSServices.provideAPIKey(key)
```

`Info.plist` 新增：
```xml
<key>MAPS_API_KEY_IOS</key>
<string>$(MAPS_API_KEY_IOS)</string>
```

### 5.2 Flutter Backend URL + X-Api-Key

`dart_defines/prod.json`（不進 git）：
```json
{
  "BACKEND_URL": "https://ai-tour-guide-backend-xxxx-de.a.run.app",
  "API_KEY": "your-api-key-here"
}
```

`BackendClient` 從 `const String.fromEnvironment('API_KEY')` 讀取，加到每個請求 header：
```dart
'X-Api-Key': _apiKey,
```

`dart_defines/dev.json` 加入 `"API_KEY": "dev"`（配合後端本地開發 `API_KEY=dev`）。

### 5.3 .gitignore 補充

```gitignore
# API Keys
flutter_app/android/local.properties
flutter_app/ios/Flutter/Debug.xcconfig
flutter_app/ios/Flutter/Release.xcconfig
dart_defines/prod.json
scripts/.env
```

---

## 6. SETUP.md（根目錄）

提供給未來自己或協作者的完整設定指引：

1. 前置需求（gcloud、Flutter、Python 3.12）
2. GCP 設定（執行 `scripts/setup-gcp.sh`）
3. API Keys 取得（每個 key 的 Console 路徑）
4. 本地開發啟動（backend + flutter run）
5. 部署（`scripts/deploy-backend.sh`）

---

## 7. 測試策略

| 層級 | 新增測試 |
|---|---|
| Unit | `NotificationService` fake 的 `showPoiTrigger` 呼叫計數；`TriggerNotifier` 在背景狀態下改呼叫 notification |
| Widget | `HomeScreen` 顯示「一律允許」dialog 的邏輯 |
| 手動 | 真機鎖屏走近 POI → 收到通知 → 點擊開啟旁白 |

現有 77 個 Flutter tests 和 195 個後端 tests 不受影響（`FakeNotificationService` 注入）。

---

## 8. 交付物清單

| 項目 | 路徑 |
|---|---|
| Dockerfile | `backend/Dockerfile` |
| .dockerignore | `backend/.dockerignore` |
| GCP 設定腳本 | `scripts/setup-gcp.sh` |
| 部署腳本 | `scripts/deploy-backend.sh` |
| NotificationService | `flutter_app/lib/shared/notification/notification_service.dart` |
| LocationService 升級 | `flutter_app/lib/shared/location/location_service.dart` |
| TriggerNotifier 整合 | `flutter_app/lib/features/narration/providers/trigger_provider.dart` |
| HomeScreen 權限 UI | `flutter_app/lib/features/session/screens/home_screen.dart` |
| Android 平台設定 | `flutter_app/android/app/src/main/AndroidManifest.xml` + `build.gradle` |
| iOS 平台設定 | `flutter_app/ios/Runner/Info.plist` + `AppDelegate.swift` |
| BackendClient 更新 | `flutter_app/lib/shared/backend/backend_client.dart` |
| X-Api-Key middleware | `backend/src/tour_guide/main.py` |
| prod dart-define 範本 | `dart_defines/prod.json.example` |
| 設定文件 | `SETUP.md` |

---

## 9. 完成標準

- [ ] `flutter test` 77+ tests pass（含新增 notification tests）
- [ ] `pytest` 195+ tests pass
- [ ] `flutter analyze` 無 error/warning
- [ ] Android 真機：鎖屏 → 走近 POI → 收到通知 → 點擊 → 旁白播放
- [ ] iOS 真機：同上
- [ ] `curl https://<cloud-run-url>/health` 回 `{"status":"ok"}`
- [ ] `curl -H "X-Api-Key: wrong" https://<url>/health` 仍 200（health 不驗證）；`/poi/nearby` 回 401

---

## 文件結束
