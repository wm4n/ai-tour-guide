# Plan F — 背景定位 + 部署上線 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 App 在螢幕鎖定時持續偵測位置並顯示本地通知，並把後端容器化部署到 Cloud Run。

**Architecture:** `geolocator` 開啟背景模式（AndroidSettings foregroundNotificationConfig + AppleSettings allowBackgroundLocationUpdates），`TriggerNotifier` 依 `appLifecycleStateProvider` 判斷前景/背景：前景觸發旁白，背景顯示本地通知。後端用 Dockerfile 部署到 Cloud Run，透過 `X-Api-Key` header 輕量保護。

**Tech Stack:** Flutter 3.x / Dart 3.x / geolocator 13.x / flutter_local_notifications / FastAPI / Docker / Cloud Run / gcloud CLI

---

## File Map

**Backend（新增/修改）：**
- Modify: `backend/src/tour_guide/config.py` — 新增 `api_key` 欄位
- Modify: `backend/src/tour_guide/main.py` — 新增 X-Api-Key middleware
- Modify: `backend/.env.example` — 新增 `API_KEY=`
- Modify: `backend/tests/integration/test_app_factory.py` — middleware 測試
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

**Flutter 邏輯（新增/修改）：**
- Modify: `flutter_app/pubspec.yaml` — 新增 `flutter_local_notifications`
- Create: `flutter_app/lib/shared/notification/notification_service.dart`
- Modify: `flutter_app/lib/shared/providers.dart` — 新增 `notificationServiceProvider` + `appLifecycleStateProvider`
- Modify: `flutter_app/lib/shared/location/location_service.dart` — 新增 `checkPermission()` + 背景 LocationSettings
- Modify: `flutter_app/lib/shared/backend/backend_client.dart` — 新增 `apiKey` + X-Api-Key header
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart` — 背景時呼叫 notification
- Modify: `flutter_app/lib/features/session/screens/home_screen.dart` — always 權限 SnackBar
- Modify: `flutter_app/lib/app.dart` — 轉為 ConsumerStatefulWidget + lifecycle observer + NotificationService.init()

**Flutter 測試（新增/修改）：**
- Create: `flutter_app/test/unit/notification_service_test.dart`
- Modify: `flutter_app/test/unit/trigger_provider_test.dart` — 新增 notificationServiceProvider override
- Modify: `flutter_app/test/widget/home_screen_test.dart` — 新增 checkPermission() + notificationServiceProvider

**Flutter 平台：**
- Modify: `flutter_app/android/app/src/main/AndroidManifest.xml`
- Modify: `flutter_app/android/app/build.gradle.kts`
- Modify: `flutter_app/android/local.properties` — 新增 `MAPS_API_KEY_ANDROID=`（本地，不進 git）
- Modify: `flutter_app/ios/Runner/Info.plist`
- Modify: `flutter_app/ios/Runner/AppDelegate.swift`
- Modify: `flutter_app/ios/Flutter/Debug.xcconfig` — 新增 `#include? "LocalConfig.xcconfig"`
- Modify: `flutter_app/ios/Flutter/Release.xcconfig` — 同上
- Create: `flutter_app/ios/Flutter/LocalConfig.xcconfig.example`（進 git，範本）
- Modify: `flutter_app/dart_defines/dev.json` — 新增 `API_KEY`

**Scripts + Docs（新增）：**
- Create: `scripts/setup-gcp.sh`
- Create: `scripts/deploy-backend.sh`
- Create: `flutter_app/dart_defines/prod.json.example`
- Create: `SETUP.md`
- Modify: `.gitignore` — 新增 `dart_defines/prod.json`、`ios/Flutter/LocalConfig.xcconfig`

---

## Task 1: Backend — api_key config + X-Api-Key middleware

**Files:**
- Modify: `backend/src/tour_guide/config.py`
- Modify: `backend/src/tour_guide/main.py`
- Modify: `backend/.env.example`
- Modify: `backend/tests/integration/test_app_factory.py`

- [ ] **Step 1: 寫失敗測試（middleware 拒絕錯誤 key）**

在 `backend/tests/integration/test_app_factory.py` 的 `TestAppFactory` class 末尾新增：

```python
def test_protected_endpoint_rejects_wrong_key(self, monkeypatch):
    """API_KEY 設定時，wrong key 回 401。"""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("API_KEY", "secret-key")
    config = AppConfig()
    app = create_app(config)
    client = TestClient(app)
    response = client.get(
        "/poi/nearby?lat=25&lon=121&radius=500&lang=zh-TW&persona=history_uncle",
        headers={"X-Api-Key": "wrong"},
    )
    assert response.status_code == 401

def test_protected_endpoint_accepts_correct_key(self, monkeypatch):
    """API_KEY 設定時，正確 key 不回 401。"""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("API_KEY", "secret-key")
    config = AppConfig()
    app = create_app(config)
    client = TestClient(app)
    response = client.get(
        "/poi/nearby?lat=25&lon=121&radius=500&lang=zh-TW&persona=history_uncle",
        headers={"X-Api-Key": "secret-key"},
    )
    assert response.status_code != 401

def test_health_skips_api_key_check(self, monkeypatch):
    """API_KEY 設定時，/health 不需要 key。"""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("API_KEY", "secret-key")
    config = AppConfig()
    app = create_app(config)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200

def test_no_api_key_config_allows_all(self, monkeypatch):
    """API_KEY 未設定（空字串），所有 endpoint 不需要 key。"""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    config = AppConfig()
    assert config.api_key == ""
    app = create_app(config)
    client = TestClient(app)
    response = client.get(
        "/poi/nearby?lat=25&lon=121&radius=500&lang=zh-TW&persona=history_uncle",
    )
    assert response.status_code != 401
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
cd backend && .venv/bin/pytest tests/integration/test_app_factory.py -v -k "api_key"
```

Expected: `AttributeError: 'AppConfig' object has no attribute 'api_key'`

- [ ] **Step 3: 新增 api_key 到 config**

`backend/src/tour_guide/config.py` 在 `log_level` 欄位之後新增：

```python
api_key: str = Field("", alias="API_KEY")
```

完整檔案：

```python
"""Configuration for the Tour Guide backend."""

from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    host: str = Field("0.0.0.0", alias="HOST")  # noqa: S104
    port: int = Field(8000, alias="PORT")
    poi_cache_dir: str = Field(
        "/tmp/tour_guide_cache",  # noqa: S108
        alias="POI_CACHE_DIR",
    )
    narration_cache_dir: str = Field(
        "/tmp/tour_guide_narration_cache",  # noqa: S108
        alias="NARRATION_CACHE_DIR",
    )
    google_places_api_key: str = Field("", alias="GOOGLE_PLACES_API_KEY")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    api_key: str = Field("", alias="API_KEY")

    model_config = {"populate_by_name": True, "env_prefix": ""}
```

- [ ] **Step 4: 新增 middleware 到 main.py**

`backend/src/tour_guide/main.py` 修改 `create_app`，在 `app = FastAPI(...)` 之後，`app.dependency_overrides[...]` 之前加入：

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
```

（在檔案頂部補 import，已有 `FastAPI` 就只補 `Request` 和 `JSONResponse`）

在 `app = FastAPI(title="AI Tour Guide", lifespan=lifespan)` 之後插入：

```python
    @app.middleware("http")
    async def verify_api_key(request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        if config.api_key and request.headers.get("X-Api-Key") != config.api_key:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
        return await call_next(request)
```

完整 `create_app` 函式頂部 imports（加到 main.py 頂部現有 imports 中）：

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
```

- [ ] **Step 5: 更新 .env.example**

`backend/.env.example` 末尾新增：

```
# X-Api-Key protection (leave empty to disable in dev)
API_KEY=
```

- [ ] **Step 6: 跑測試，確認通過**

```bash
cd backend && .venv/bin/pytest tests/integration/test_app_factory.py -v
```

Expected: 全部 PASS（新增 4 個 + 原有全部通過）

- [ ] **Step 7: Commit**

```bash
cd backend
git add src/tour_guide/config.py src/tour_guide/main.py .env.example tests/integration/test_app_factory.py
git commit -m "feat(backend): add api_key config + X-Api-Key middleware (dev skip when empty)"
```

---

## Task 2: Backend — Dockerfile + .dockerignore

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

- [ ] **Step 1: 建立 Dockerfile**

`backend/Dockerfile`：

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

- [ ] **Step 2: 建立 .dockerignore**

`backend/.dockerignore`：

```
.venv/
__pycache__/
*.pyc
*.pyo
tests/
.env
.env.*
.ruff_cache/
.pytest_cache/
htmlcov/
.coverage
*.egg-info/
```

- [ ] **Step 3: 確認後端測試仍通過**

```bash
cd backend && .venv/bin/pytest -v
```

Expected: 195+ tests PASS

- [ ] **Step 4: Commit**

```bash
cd backend
git add Dockerfile .dockerignore
git commit -m "feat(backend): add Dockerfile and .dockerignore for Cloud Run deployment"
```

---

## Task 3: Flutter — 新增 flutter_local_notifications

**Files:**
- Modify: `flutter_app/pubspec.yaml`

- [ ] **Step 1: 新增 dependency**

`flutter_app/pubspec.yaml` 的 `dependencies:` 區塊新增一行：

```yaml
  flutter_local_notifications: ^17.2.4
```

完整 dependencies 區塊（在 `record: ^5.0.0` 之後新增）：

```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.6.0
  google_maps_flutter: ^2.10.0
  geolocator: ^13.0.0
  permission_handler: ^11.3.0
  just_audio: ^0.9.40
  drift: ^2.18.0
  drift_flutter: ^0.2.0
  http: ^1.2.0
  http_parser: ^4.0.0
  go_router: ^14.3.0
  path_provider: ^2.1.3
  record: ^5.0.0
  flutter_local_notifications: ^17.2.4
```

- [ ] **Step 2: 取得 package**

```bash
cd flutter_app && flutter pub get
```

Expected: `Got dependencies!`（無 version conflict）

- [ ] **Step 3: Commit**

```bash
cd flutter_app
git add pubspec.yaml pubspec.lock
git commit -m "feat(flutter): add flutter_local_notifications dependency"
```

---

## Task 4: Flutter — NotificationService（abstract + Fake + Real）

**Files:**
- Create: `flutter_app/lib/shared/notification/notification_service.dart`
- Create: `flutter_app/test/unit/notification_service_test.dart`

- [ ] **Step 1: 寫失敗測試**

建立 `flutter_app/test/unit/notification_service_test.dart`：

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';

void main() {
  const testPoi = POI(
    id: 'osm:test',
    name: '測試景點',
    lat: 25.0,
    lon: 121.0,
    tags: {},
    distanceM: 80,
    confidence: 'high',
  );

  group('FakeNotificationService', () {
    test('init() completes without error', () async {
      final svc = FakeNotificationService();
      await expectLater(svc.init(), completes);
    });

    test('showPoiTrigger() records the poi', () async {
      final svc = FakeNotificationService();
      await svc.showPoiTrigger(testPoi);
      expect(svc.shown, contains(testPoi));
    });

    test('showPoiTrigger() called twice records both', () async {
      final svc = FakeNotificationService();
      const poi2 = POI(
        id: 'osm:test2',
        name: '另一景點',
        lat: 25.1,
        lon: 121.1,
        tags: {},
        distanceM: 60,
        confidence: 'medium',
      );
      await svc.showPoiTrigger(testPoi);
      await svc.showPoiTrigger(poi2);
      expect(svc.shown, hasLength(2));
    });
  });
}
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
cd flutter_app && flutter test test/unit/notification_service_test.dart
```

Expected: `Error: 'package:flutter_app/shared/notification/notification_service.dart' doesn't exist`

- [ ] **Step 3: 建立 NotificationService**

建立 `flutter_app/lib/shared/notification/notification_service.dart`：

```dart
import 'dart:io';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';

abstract class NotificationService {
  Future<void> init();
  Future<void> showPoiTrigger(POI poi);
}

class FakeNotificationService implements NotificationService {
  final List<POI> shown = [];

  @override
  Future<void> init() async {}

  @override
  Future<void> showPoiTrigger(POI poi) async {
    shown.add(poi);
  }
}

class RealNotificationService implements NotificationService {
  final _plugin = FlutterLocalNotificationsPlugin();

  @override
  Future<void> init() async {
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const ios = DarwinInitializationSettings(requestAlertPermission: true);
    await _plugin.initialize(
      const InitializationSettings(android: android, iOS: ios),
    );

    if (Platform.isAndroid) {
      const channel = AndroidNotificationChannel(
        'poi_triggers',
        'POI 景點提醒',
        description: '走近景點時的通知',
        importance: Importance.high,
      );
      await _plugin
          .resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>()
          ?.createNotificationChannel(channel);
    }
  }

  @override
  Future<void> showPoiTrigger(POI poi) async {
    const android = AndroidNotificationDetails(
      'poi_triggers',
      'POI 景點提醒',
      channelDescription: '走近景點時的通知',
      importance: Importance.high,
      priority: Priority.high,
    );
    const ios = DarwinNotificationDetails();
    await _plugin.show(
      poi.id.hashCode,
      '🗺 你附近有景點',
      poi.name,
      const NotificationDetails(android: android, iOS: ios),
    );
  }
}
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
cd flutter_app && flutter test test/unit/notification_service_test.dart
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd flutter_app
git add lib/shared/notification/notification_service.dart test/unit/notification_service_test.dart
git commit -m "feat(flutter): add NotificationService with Fake and Real implementations (TDD)"
```

---

## Task 5: Flutter — providers.dart 新增 notificationServiceProvider + appLifecycleStateProvider

**Files:**
- Modify: `flutter_app/lib/shared/providers.dart`

- [ ] **Step 1: 更新 providers.dart**

`flutter_app/lib/shared/providers.dart` 完整替換為：

```dart
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';

const _backendUrl = String.fromEnvironment(
  'BACKEND_URL',
  defaultValue: 'http://localhost:8000',
);

const _apiKey = String.fromEnvironment('API_KEY', defaultValue: '');

final backendClientProvider = Provider<BackendClient>((ref) {
  return RealBackendClient(baseUrl: _backendUrl, apiKey: _apiKey);
});

final locationServiceProvider = Provider<LocationService>((ref) {
  return RealLocationService();
});

final localDbProvider = Provider<LocalDb>((ref) {
  final db = LocalDb();
  ref.onDispose(db.close);
  return db;
});

final audioPlayerServiceProvider = Provider<AudioPlayerService>((ref) {
  final service = RealAudioPlayerService();
  ref.onDispose(service.dispose);
  return service;
});

// 旁白 AudioPlayer 的別名（語意更清楚）
final narrationAudioPlayerProvider = audioPlayerServiceProvider;

// Q&A 專用 AudioPlayer（獨立實例，不影響旁白音量）
final qaAudioPlayerProvider = Provider<AudioPlayerService>((ref) {
  final service = RealAudioPlayerService();
  ref.onDispose(service.dispose);
  return service;
});

final micRecorderProvider = Provider<MicRecorderService>((ref) {
  final service = RealMicRecorderService();
  ref.onDispose(service.dispose);
  return service;
});

final notificationServiceProvider = Provider<NotificationService>((ref) {
  return RealNotificationService();
});

// App lifecycle state — updated by App widget's WidgetsBindingObserver
final appLifecycleStateProvider =
    StateProvider<AppLifecycleState>((ref) => AppLifecycleState.resumed);
```

- [ ] **Step 2: 確認 Flutter 分析無 error**

```bash
cd flutter_app && flutter analyze lib/shared/providers.dart
```

Expected: `No issues found!`

- [ ] **Step 3: 跑全部測試確認無破壞**

```bash
cd flutter_app && flutter test
```

Expected: 77 tests PASS（可能有幾個因為 override 缺少 notificationServiceProvider 而新增警告，但不應有 FAIL）

- [ ] **Step 4: Commit**

```bash
cd flutter_app
git add lib/shared/providers.dart
git commit -m "feat(flutter): add notificationServiceProvider and appLifecycleStateProvider to providers"
```

---

## Task 6: Flutter — LocationService 新增 checkPermission() + 背景 LocationSettings

**Files:**
- Modify: `flutter_app/lib/shared/location/location_service.dart`

- [ ] **Step 1: 更新 location_service.dart**

完整替換 `flutter_app/lib/shared/location/location_service.dart`：

```dart
import 'dart:async';
import 'dart:io';
import 'package:geolocator/geolocator.dart';

abstract class LocationService {
  Future<bool> requestPermission();
  Future<LocationPermission> checkPermission();
  void start();
  void stop();
  Stream<Position> get positionStream;
}

class RealLocationService implements LocationService {
  StreamController<Position>? _controller;
  StreamSubscription<Position>? _subscription;

  @override
  Future<bool> requestPermission() async {
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
    }
    return perm == LocationPermission.whileInUse ||
        perm == LocationPermission.always;
  }

  @override
  Future<LocationPermission> checkPermission() => Geolocator.checkPermission();

  @override
  void start() {
    _controller = StreamController<Position>.broadcast();
    final LocationSettings settings;
    if (Platform.isIOS) {
      settings = const AppleSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10,
        allowBackgroundLocationUpdates: true,
        pauseLocationUpdatesAutomatically: false,
      );
    } else {
      settings = const AndroidSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10,
        foregroundNotificationConfig: ForegroundNotificationConfig(
          notificationTitle: 'AI Tour Guide',
          notificationText: '正在偵測附近景點...',
          enableWakeLock: true,
        ),
      );
    }
    _subscription = Geolocator.getPositionStream(
      locationSettings: settings,
    ).listen(
      _controller!.add,
      onError: _controller!.addError,
    );
  }

  @override
  void stop() {
    _subscription?.cancel();
    _subscription = null;
    _controller?.close();
    _controller = null;
  }

  @override
  Stream<Position> get positionStream =>
      _controller?.stream ?? const Stream.empty();
}

class FakeLocationService implements LocationService {
  final StreamController<Position> _controller =
      StreamController<Position>.broadcast();
  final bool _hasPermission;

  FakeLocationService({bool hasPermission = true})
      : _hasPermission = hasPermission;

  void emit(Position position) => _controller.add(position);

  @override
  Future<bool> requestPermission() async => _hasPermission;

  @override
  Future<LocationPermission> checkPermission() async =>
      _hasPermission ? LocationPermission.always : LocationPermission.denied;

  @override
  void start() {}

  @override
  void stop() {}

  @override
  Stream<Position> get positionStream => _controller.stream;
}

Position fakePosition(double lat, double lon) => Position(
      latitude: lat,
      longitude: lon,
      timestamp: DateTime.now(),
      accuracy: 5,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 0,
      headingAccuracy: 0,
      speed: 0,
      speedAccuracy: 0,
    );
```

- [ ] **Step 2: 跑全部 Flutter 測試**

```bash
cd flutter_app && flutter test
```

Expected: 77 tests PASS（無新 FAIL）

- [ ] **Step 3: Commit**

```bash
cd flutter_app
git add lib/shared/location/location_service.dart
git commit -m "feat(flutter): LocationService background settings (AndroidSettings/AppleSettings) + checkPermission()"
```

---

## Task 7: Flutter — BackendClient 新增 X-Api-Key header

**Files:**
- Modify: `flutter_app/lib/shared/backend/backend_client.dart`

- [ ] **Step 1: 修改 RealBackendClient**

`flutter_app/lib/shared/backend/backend_client.dart` 中，修改 `RealBackendClient` 部分：

**constructor 改為：**

```dart
class RealBackendClient implements BackendClient {
  final String baseUrl;
  final String apiKey;
  final http.Client _http;

  RealBackendClient({required this.baseUrl, this.apiKey = ''})
      : _http = http.Client();

  Map<String, String> get _authHeaders => {
        if (apiKey.isNotEmpty) 'X-Api-Key': apiKey,
      };
```

**fetchNearby 的 `_http.get(uri)` 改為：**

```dart
    final response = await _http.get(uri, headers: _authHeaders);
```

**narrate 在 `request.headers['Accept'] = ...` 之前加：**

```dart
    _authHeaders.forEach((k, v) => request.headers[k] = v);
```

（放在 `request.headers['Content-Type'] = 'application/json';` 之後）

**qa 在 `request.headers['Accept'] = ...` 之前加：**

```dart
    _authHeaders.forEach((k, v) => request.headers[k] = v);
```

（放在 `request.headers['Accept'] = 'text/event-stream';` 之後）

- [ ] **Step 2: 跑全部 Flutter 測試**

```bash
cd flutter_app && flutter test
```

Expected: 77 tests PASS（FakeBackendClient 不受影響）

- [ ] **Step 3: Commit**

```bash
cd flutter_app
git add lib/shared/backend/backend_client.dart
git commit -m "feat(flutter): BackendClient sends X-Api-Key header when API_KEY dart-define is set"
```

---

## Task 8: Flutter — TriggerNotifier 背景時呼叫 NotificationService

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **Step 1: 先更新測試，補 notificationServiceProvider override**

`flutter_app/test/unit/trigger_provider_test.dart` 完整替換為：

```dart
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';
import 'package:flutter_app/shared/providers.dart';

void main() {
  const nearPoi = POI(
    id: 'osm:near',
    name: '近處景點',
    lat: 25.1031,
    lon: 121.5482,
    tags: {},
    distanceM: 89,
    confidence: 'high',
  );

  ProviderContainer _makeContainer({bool backgroundMode = false}) {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final fakeNotification = FakeNotificationService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    return ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(
          const FakeBackendClient(nearbyPois: [nearPoi]),
        ),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
        notificationServiceProvider.overrideWithValue(fakeNotification),
        if (backgroundMode)
          appLifecycleStateProvider.overrideWith(
            (ref) => AppLifecycleState.paused,
          ),
      ],
    );
  }

  test('TriggerProvider activates without exception (foreground)', () async {
    final container = _makeContainer();
    addTearDown(container.dispose);

    final fakeLocation = container.read(locationServiceProvider) as FakeLocationService;
    container.read(triggerProvider);
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    container.read(triggerProvider);
    expect(true, isTrue);
  });

  test('TriggerProvider calls notification when app is in background', () async {
    final container = _makeContainer(backgroundMode: true);
    addTearDown(container.dispose);

    final fakeLocation = container.read(locationServiceProvider) as FakeLocationService;
    final fakeNotif = container.read(notificationServiceProvider) as FakeNotificationService;

    container.read(triggerProvider);
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 100));

    expect(fakeNotif.shown, isNotEmpty);
  });
}
```

- [ ] **Step 2: 跑測試，確認失敗（background test 失敗因 trigger_provider 未實作）**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart
```

Expected: 第一個 PASS，第二個 FAIL（`shown` 仍為空）

- [ ] **Step 3: 更新 TriggerNotifier**

`flutter_app/lib/features/narration/providers/trigger_provider.dart` 完整替換為：

```dart
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/trigger_engine.dart';
import 'package:flutter_app/features/session/persona_data.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/providers.dart';

class TriggerNotifier extends Notifier<void> {
  final Set<String> _sessionPlayedIds = {};

  @override
  void build() {
    final positionAsync = ref.watch(positionStreamProvider);
    final poisAsync = ref.watch(poiProvider);

    positionAsync.whenData((position) {
      poisAsync.whenData((pois) {
        _evaluate(position, pois);
      });
    });
  }

  Future<void> _evaluate(Position position, List<dynamic> pois) async {
    final narState = ref.read(narrationProvider);
    if (narState.status == NarrationStatus.playing ||
        narState.status == NarrationStatus.loading) {
      return;
    }

    final db = ref.read(localDbProvider);
    final cooldownIds = <String>{};
    for (final poi in pois) {
      final inCooldown =
          await db.isCooldown(poi.id, const Duration(hours: 24));
      if (inCooldown) cooldownIds.add(poi.id);
    }

    final session = ref.read(sessionProvider);
    final personaInfo = kPersonas.firstWhere(
      (p) => p.id == session.persona,
      orElse: () => kPersonas.first,
    );
    final triggerRadiusM = personaInfo.defaultTriggerRadiusM.toDouble();

    final triggers = TriggerEngine.evaluate(
      userLat: position.latitude,
      userLon: position.longitude,
      pois: pois.cast(),
      playedPoiIds: _sessionPlayedIds,
      cooldownPoiIds: cooldownIds,
      radiusM: triggerRadiusM,
    );

    if (triggers.isNotEmpty) {
      final poi = triggers.first;
      _sessionPlayedIds.add(poi.id);

      final lifecycleState = ref.read(appLifecycleStateProvider);
      final isBackground = lifecycleState != AppLifecycleState.resumed;

      if (isBackground) {
        await ref.read(notificationServiceProvider).showPoiTrigger(poi);
      } else {
        ref.read(narrationProvider.notifier).narrate(
          poi,
          persona: session.persona,
          lang: session.lang,
        );
      }
    }
  }
}

final triggerProvider = NotifierProvider<TriggerNotifier, void>(
  TriggerNotifier.new,
);
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
cd flutter_app
git add lib/features/narration/providers/trigger_provider.dart test/unit/trigger_provider_test.dart
git commit -m "feat(flutter): TriggerNotifier routes to notification when app is backgrounded"
```

---

## Task 9: Flutter — HomeScreen always 權限 SnackBar

**Files:**
- Modify: `flutter_app/lib/features/session/screens/home_screen.dart`
- Modify: `flutter_app/test/widget/home_screen_test.dart`

- [ ] **Step 1: 更新 home_screen_test.dart，補 checkPermission + notificationServiceProvider**

`flutter_app/test/widget/home_screen_test.dart` 中，修改 `_FakeLocationService` 增加 `checkPermission`，並更新 `_makeWidget` 補 notification override。

找到 `_FakeLocationService` class，替換為：

```dart
class _FakeLocationService implements LocationService {
  final bool hasPermission;
  final bool isAlwaysPermission;

  _FakeLocationService({
    this.hasPermission = true,
    this.isAlwaysPermission = true,
  });

  @override
  Future<bool> requestPermission() async => hasPermission;

  @override
  Future<LocationPermission> checkPermission() async =>
      isAlwaysPermission ? LocationPermission.always : LocationPermission.whileInUse;

  @override
  void start() {}

  @override
  void stop() {}

  @override
  Stream<Position> get positionStream => const Stream.empty();
}
```

找到 `_makeWidget` 函式，替換為：

```dart
Widget _makeWidget({bool hasPermission = true, bool isAlwaysPermission = true}) {
  return ProviderScope(
    overrides: [
      locationServiceProvider.overrideWithValue(
        _FakeLocationService(
          hasPermission: hasPermission,
          isAlwaysPermission: isAlwaysPermission,
        ),
      ),
      localDbProvider.overrideWithValue(
        LocalDb.forTesting(NativeDatabase.memory()),
      ),
      notificationServiceProvider.overrideWithValue(
        FakeNotificationService(),
      ),
    ],
    child: const MaterialApp(home: HomeScreen()),
  );
}
```

在 `home_screen_test.dart` 頂部 imports 新增：

```dart
import 'package:flutter_app/shared/notification/notification_service.dart';
```

- [ ] **Step 2: 新增 whileInUse 警告測試**

在現有測試末尾新增（`flutter_app/test/widget/home_screen_test.dart`）：

```dart
  testWidgets('shows snackbar when permission is whileInUse only', (tester) async {
    await tester.pumpWidget(_makeWidget(
      hasPermission: true,
      isAlwaysPermission: false,
    ));
    await tester.tap(find.text('開始旅程'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(SnackBar), findsOneWidget);
    expect(find.textContaining('一律允許'), findsOneWidget);
  });
```

- [ ] **Step 3: 跑 widget 測試，確認新測試失敗**

```bash
cd flutter_app && flutter test test/widget/home_screen_test.dart
```

Expected: 現有測試 PASS，新測試 FAIL

- [ ] **Step 4: 更新 HomeScreen._start()**

`flutter_app/lib/features/session/screens/home_screen.dart` 中，替換 `_start` 方法：

```dart
  Future<void> _start(BuildContext context, WidgetRef ref) async {
    await ref.read(sessionProvider.notifier).start();
    if (!context.mounted) return;
    final status = ref.read(sessionProvider).status;
    if (status == SessionStatus.active) {
      final locationService = ref.read(locationServiceProvider);
      final perm = await locationService.checkPermission();
      if (context.mounted && perm == LocationPermission.whileInUse) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('建議設定為「一律允許」定位，以便鎖屏時收到景點通知'),
            action: SnackBarAction(
              label: '設定',
              onPressed: () => Geolocator.openAppSettings(),
            ),
            duration: const Duration(seconds: 8),
          ),
        );
      }
      if (context.mounted) context.push('/map');
    } else if (status == SessionStatus.idle) {
      showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('需要定位權限'),
          content: const Text('請在設定中允許「使用 App 期間」的定位權限。'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('確定'),
            ),
          ],
        ),
      );
    }
  }
```

檔案頂部確認有 `import 'package:geolocator/geolocator.dart';`（已有）。

- [ ] **Step 5: 跑全部 widget 測試**

```bash
cd flutter_app && flutter test test/widget/home_screen_test.dart
```

Expected: 全部 PASS

- [ ] **Step 6: 跑全部 Flutter 測試**

```bash
cd flutter_app && flutter test
```

Expected: 78+ tests PASS（新增 1 個 widget test）

- [ ] **Step 7: Commit**

```bash
cd flutter_app
git add lib/features/session/screens/home_screen.dart test/widget/home_screen_test.dart
git commit -m "feat(flutter): HomeScreen shows snackbar when location permission is whileInUse only"
```

---

## Task 10: Flutter — App widget 轉換為 lifecycle observer + NotificationService init

**Files:**
- Modify: `flutter_app/lib/app.dart`

- [ ] **Step 1: 更新 app.dart**

完整替換 `flutter_app/lib/app.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/features/session/screens/home_screen.dart';
import 'package:flutter_app/features/map/screens/map_screen.dart';
import 'package:flutter_app/shared/providers.dart';

final _router = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (_, __) => const HomeScreen(),
    ),
    GoRoute(
      path: '/map',
      builder: (_, __) => const MapScreen(),
    ),
  ],
);

class App extends ConsumerStatefulWidget {
  const App({super.key});

  @override
  ConsumerState<App> createState() => _AppState();
}

class _AppState extends ConsumerState<App> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    ref.read(notificationServiceProvider).init();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    ref.read(appLifecycleStateProvider.notifier).state = state;
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'AI Tour Guide',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF4A9EFF),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      routerConfig: _router,
    );
  }
}
```

- [ ] **Step 2: 跑全部 Flutter 測試**

```bash
cd flutter_app && flutter test
```

Expected: 78+ tests PASS

- [ ] **Step 3: 確認 flutter analyze 無 error**

```bash
cd flutter_app && flutter analyze
```

Expected: 無 error，最多 info 等級 warning

- [ ] **Step 4: Commit**

```bash
cd flutter_app
git add lib/app.dart
git commit -m "feat(flutter): App widget registers lifecycle observer and initializes NotificationService"
```

---

## Task 11: Android 平台設定

**Files:**
- Modify: `flutter_app/android/app/src/main/AndroidManifest.xml`
- Modify: `flutter_app/android/app/build.gradle.kts`
- Modify: `flutter_app/android/local.properties`（本地，不進 git）

- [ ] **Step 1: 更新 AndroidManifest.xml**

`flutter_app/android/app/src/main/AndroidManifest.xml` 完整替換為：

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
    <uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION"/>
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
    <application
        android:label="flutter_app"
        android:name="${applicationName}"
        android:icon="@mipmap/ic_launcher">
        <meta-data
            android:name="com.google.android.geo.API_KEY"
            android:value="${MAPS_API_KEY}"/>
        <service
            android:name="com.baseflow.geolocator.GeolocatorService"
            android:foregroundServiceType="location"
            android:exported="false"/>
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTop"
            android:taskAffinity=""
            android:theme="@style/LaunchTheme"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"
            android:hardwareAccelerated="true"
            android:windowSoftInputMode="adjustResize">
            <meta-data
              android:name="io.flutter.embedding.android.NormalTheme"
              android:resource="@style/NormalTheme"
              />
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        <meta-data
            android:name="flutterEmbedding"
            android:value="2" />
    </application>
    <queries>
        <intent>
            <action android:name="android.intent.action.PROCESS_TEXT"/>
            <data android:mimeType="text/plain"/>
        </intent>
    </queries>
</manifest>
```

- [ ] **Step 2: 更新 build.gradle.kts（注入 MAPS_API_KEY）**

`flutter_app/android/app/build.gradle.kts` 頂部（`plugins {` 之前）新增：

```kotlin
import java.util.Properties

val localProps = Properties()
val localPropsFile = rootProject.file("local.properties")
if (localPropsFile.exists()) {
    localProps.load(localPropsFile.inputStream())
}
```

在 `defaultConfig { ... }` 區塊內新增一行：

```kotlin
        manifestPlaceholders["MAPS_API_KEY"] = localProps["MAPS_API_KEY_ANDROID"] as String? ?: ""
```

完整 `build.gradle.kts` 結構（只顯示需修改的關鍵位置）：

```kotlin
import java.util.Properties

val localProps = Properties()
val localPropsFile = rootProject.file("local.properties")
if (localPropsFile.exists()) {
    localProps.load(localPropsFile.inputStream())
}

plugins {
    id("com.android.application")
    id("kotlin-android")
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    // ... 現有設定不變 ...
    defaultConfig {
        applicationId = "com.example.flutter_app"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        manifestPlaceholders["MAPS_API_KEY"] = localProps["MAPS_API_KEY_ANDROID"] as String? ?: ""
    }
    // ... 其餘不變 ...
}
```

- [ ] **Step 3: 在 local.properties 加入 Maps API Key**

`flutter_app/android/local.properties`（已有 sdk.dir 等）末尾新增：

```properties
MAPS_API_KEY_ANDROID=YOUR_ANDROID_MAPS_API_KEY_HERE
```

（此時用佔位符，取得真實 key 後替換）

- [ ] **Step 4: 確認 Flutter analyze 無 error**

```bash
cd flutter_app && flutter analyze
```

Expected: 無 error

- [ ] **Step 5: Commit**

```bash
cd flutter_app
git add android/app/src/main/AndroidManifest.xml android/app/build.gradle.kts
git commit -m "feat(android): add background location permissions, foreground service, and MAPS_API_KEY injection"
```

（注意：`local.properties` 不進 git，勿加入 `git add`）

---

## Task 12: iOS 平台設定

**Files:**
- Modify: `flutter_app/ios/Runner/Info.plist`
- Modify: `flutter_app/ios/Runner/AppDelegate.swift`
- Modify: `flutter_app/ios/Flutter/Debug.xcconfig`
- Modify: `flutter_app/ios/Flutter/Release.xcconfig`
- Create: `flutter_app/ios/Flutter/LocalConfig.xcconfig.example`

- [ ] **Step 1: 更新 Info.plist（background modes + Maps key）**

`flutter_app/ios/Runner/Info.plist` 在 `<dict>` 開頭（第一個 `<key>` 之前）插入：

```xml
	<key>UIBackgroundModes</key>
	<array>
		<string>location</string>
	</array>
	<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
	<string>AI Tour Guide 需要在背景持續偵測位置，以便在你走近景點時自動顯示通知。</string>
	<key>NSLocationAlwaysUsageDescription</key>
	<string>AI Tour Guide 需要「一律允許」定位，才能在鎖屏時繼續偵測景點。</string>
	<key>NSLocationWhenInUseUsageDescription</key>
	<string>AI Tour Guide 需要定位權限才能偵測附近景點。</string>
	<key>MAPS_API_KEY_IOS</key>
	<string>$(MAPS_API_KEY_IOS)</string>
```

- [ ] **Step 2: 更新 AppDelegate.swift（從 bundle 讀 Maps key）**

`flutter_app/ios/Runner/AppDelegate.swift` 完整替換為：

```swift
import Flutter
import UIKit
import GoogleMaps

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    let mapsKey = Bundle.main.object(forInfoDictionaryKey: "MAPS_API_KEY_IOS") as? String ?? ""
    GMSServices.provideAPIKey(mapsKey)
    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
```

- [ ] **Step 3: 更新 Debug.xcconfig 和 Release.xcconfig（optional include）**

`flutter_app/ios/Flutter/Debug.xcconfig` 末尾新增一行：

```
#include? "LocalConfig.xcconfig"
```

`flutter_app/ios/Flutter/Release.xcconfig` 末尾新增一行：

```
#include? "LocalConfig.xcconfig"
```

（`?` 表示檔案不存在時不報錯）

- [ ] **Step 4: 建立 LocalConfig.xcconfig.example（進 git）**

建立 `flutter_app/ios/Flutter/LocalConfig.xcconfig.example`：

```
// 複製此檔案為 LocalConfig.xcconfig（同目錄），填入真實 API Key。
// LocalConfig.xcconfig 已加入 .gitignore，請勿 commit。
MAPS_API_KEY_IOS=YOUR_IOS_MAPS_API_KEY_HERE
```

- [ ] **Step 5: 建立本地 LocalConfig.xcconfig（不進 git）**

```bash
cp flutter_app/ios/Flutter/LocalConfig.xcconfig.example flutter_app/ios/Flutter/LocalConfig.xcconfig
```

然後編輯 `flutter_app/ios/Flutter/LocalConfig.xcconfig`，填入真實 iOS Maps API Key（取得 key 之後再填）。

- [ ] **Step 6: Commit（不含 LocalConfig.xcconfig）**

```bash
cd flutter_app
git add ios/Runner/Info.plist ios/Runner/AppDelegate.swift
git add ios/Flutter/Debug.xcconfig ios/Flutter/Release.xcconfig
git add ios/Flutter/LocalConfig.xcconfig.example
git commit -m "feat(ios): add background location modes, NSLocation descriptions, Maps API key from xcconfig"
```

---

## Task 13: .gitignore 更新 + dart_defines/dev.json

**Files:**
- Modify: `.gitignore`（根目錄）
- Modify: `flutter_app/dart_defines/dev.json`

- [ ] **Step 1: 更新根目錄 .gitignore**

`.gitignore` 末尾新增：

```gitignore
# Plan F — 本地設定（不含真實 API Key）
flutter_app/dart_defines/prod.json
flutter_app/ios/Flutter/LocalConfig.xcconfig
scripts/.env
```

- [ ] **Step 2: 更新 dart_defines/dev.json**

`flutter_app/dart_defines/dev.json` 完整替換為：

```json
{
  "BACKEND_URL": "http://10.0.2.2:8000",
  "API_KEY": "dev"
}
```

（iOS simulator 用 `--dart-define=BACKEND_URL=http://localhost:8000 --dart-define=API_KEY=dev`）

- [ ] **Step 3: 確認 prod.json 不在 git 追蹤中**

```bash
cd flutter_app && git status dart_defines/
```

Expected: `dart_defines/dev.json` 顯示為 modified，`dart_defines/prod.json`（若有）不應出現（gitignored）

- [ ] **Step 4: Commit**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide
git add .gitignore flutter_app/dart_defines/dev.json
git commit -m "chore: gitignore prod.json and LocalConfig.xcconfig; add API_KEY to dev dart-define"
```

---

## Task 14: Scripts — setup-gcp.sh + deploy-backend.sh

**Files:**
- Create: `scripts/setup-gcp.sh`
- Create: `scripts/deploy-backend.sh`

- [ ] **Step 1: 建立 scripts/ 目錄並建立 setup-gcp.sh**

```bash
mkdir -p /Users/william.chao/workspace/flutter/ai-tour-guide/scripts
```

建立 `scripts/setup-gcp.sh`：

```bash
#!/usr/bin/env bash
# setup-gcp.sh — 建立 GCP 專案並啟用 Plan F 所需的所有 API
# 執行前確認：gcloud CLI 已安裝並登入
set -euo pipefail

REGION="asia-east1"
SUFFIX=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 6)
PROJECT_ID="ai-tour-guide-${SUFFIX}"
REPO_NAME="tour-guide"
SERVICE_ACCOUNT="tour-guide-runner"

echo "=== AI Tour Guide GCP 設定 ==="
echo "Project ID: ${PROJECT_ID}"
echo ""

# 1. 建立專案
echo "1. 建立 GCP 專案..."
gcloud projects create "${PROJECT_ID}" --name="AI Tour Guide"
gcloud config set project "${PROJECT_ID}"

# 2. 提示綁定 Billing
echo ""
echo "⚠️  請前往以下網址為專案綁定 Billing Account："
echo "   https://console.cloud.google.com/billing/linkedaccount?project=${PROJECT_ID}"
echo ""
read -r -p "綁定完成後按 Enter 繼續..."

# 3. 啟用必要 API
echo "2. 啟用 API（需要 1-2 分鐘）..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  maps-android-backend.googleapis.com \
  maps-ios-backend.googleapis.com \
  places.googleapis.com \
  --project="${PROJECT_ID}"

# 4. 建立 Artifact Registry repo
echo "3. 建立 Artifact Registry repo..."
gcloud artifacts repositories create "${REPO_NAME}" \
  --repository-format=docker \
  --location="${REGION}" \
  --project="${PROJECT_ID}"

# 5. 設定 docker auth
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# 6. 建立 Service Account
echo "4. 建立 Service Account..."
gcloud iam service-accounts create "${SERVICE_ACCOUNT}" \
  --display-name="AI Tour Guide Cloud Run Runner" \
  --project="${PROJECT_ID}"

SA_EMAIL="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# 7. 建立 Secret Manager secret
echo ""
echo "5. 建立 API Key secret..."
read -r -s -p "請輸入你要設定的 X-Api-Key 值（不會顯示）: " API_KEY_VALUE
echo ""
echo -n "${API_KEY_VALUE}" | gcloud secrets create tour-guide-api-key \
  --data-file=- \
  --project="${PROJECT_ID}"

echo ""
echo "=== 設定完成 ==="
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/backend:latest"
echo "PROJECT_ID=${PROJECT_ID}"
echo "IMAGE_URL=${IMAGE_URL}"
echo ""
echo "下一步：執行 scripts/deploy-backend.sh 進行部署"
echo "請記錄以上資訊！"

# 輸出到 scripts/.env（gitignored）
cat > "$(dirname "$0")/.env" <<EOF
PROJECT_ID=${PROJECT_ID}
REGION=${REGION}
REPO_NAME=${REPO_NAME}
IMAGE_URL=${IMAGE_URL}
SERVICE_ACCOUNT_EMAIL=${SA_EMAIL}
EOF
echo "設定已儲存到 scripts/.env"
```

- [ ] **Step 2: 建立 deploy-backend.sh**

建立 `scripts/deploy-backend.sh`：

```bash
#!/usr/bin/env bash
# deploy-backend.sh — 建置並部署後端到 Cloud Run
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "❌ 找不到 ${ENV_FILE}，請先執行 scripts/setup-gcp.sh"
  exit 1
fi

# shellcheck source=/dev/null
source "${ENV_FILE}"

# 驗證必要環境變數
: "${GEMINI_API_KEY:?請設定 GEMINI_API_KEY 環境變數}"
: "${GOOGLE_PLACES_API_KEY:?請設定 GOOGLE_PLACES_API_KEY 環境變數（可設空字串用假資料）}"

BACKEND_DIR="${SCRIPT_DIR}/../backend"

echo "=== 部署 AI Tour Guide 後端 ==="
echo "Project: ${PROJECT_ID}"
echo "Image:   ${IMAGE_URL}"
echo ""

# 建置並推送 Docker image
echo "1. 建置 Docker image..."
gcloud builds submit "${BACKEND_DIR}" \
  --tag "${IMAGE_URL}" \
  --project="${PROJECT_ID}"

# 部署到 Cloud Run
echo "2. 部署到 Cloud Run..."
gcloud run deploy ai-tour-guide-backend \
  --image "${IMAGE_URL}" \
  --region "${REGION}" \
  --platform managed \
  --service-account "${SERVICE_ACCOUNT_EMAIL}" \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY},GOOGLE_PLACES_API_KEY=${GOOGLE_PLACES_API_KEY}" \
  --set-secrets "API_KEY=tour-guide-api-key:latest" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3 \
  --project="${PROJECT_ID}"

# 取得 Service URL
SERVICE_URL=$(gcloud run services describe ai-tour-guide-backend \
  --region "${REGION}" \
  --format "value(status.url)" \
  --project="${PROJECT_ID}")

echo ""
echo "✅ 部署完成！"
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "驗證："
echo "  curl ${SERVICE_URL}/health"
echo ""
echo "Flutter prod dart-define："
echo "  BACKEND_URL=${SERVICE_URL}"
echo "  (API_KEY 請從 Secret Manager 取得)"
```

- [ ] **Step 3: 設定執行權限**

```bash
chmod +x scripts/setup-gcp.sh scripts/deploy-backend.sh
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup-gcp.sh scripts/deploy-backend.sh
git commit -m "feat(scripts): add setup-gcp.sh and deploy-backend.sh for Cloud Run deployment"
```

---

## Task 15: 文件 — prod.json.example + SETUP.md + .env.example 更新

**Files:**
- Create: `flutter_app/dart_defines/prod.json.example`
- Create: `SETUP.md`
- Modify: `backend/.env.example`（已在 Task 1 更新）

- [ ] **Step 1: 建立 prod.json.example**

建立 `flutter_app/dart_defines/prod.json.example`：

```json
{
  "BACKEND_URL": "https://ai-tour-guide-backend-XXXX-de.a.run.app",
  "API_KEY": "your-x-api-key-here"
}
```

（執行 `deploy-backend.sh` 後，複製此檔案為 `prod.json` 並填入真實值）

- [ ] **Step 2: 建立 SETUP.md**

建立根目錄 `SETUP.md`：

```markdown
# AI Tour Guide — 設定指引

## 前置需求

- Flutter 3.x（`flutter doctor` 顯示 OK）
- Python 3.12+
- gcloud CLI（已登入：`gcloud auth login`）
- Docker（Cloud Run 部署用）

## 本地開發

### 1. 後端

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
# 在 .env 填入 GEMINI_API_KEY
GEMINI_API_KEY=your-key .venv/bin/uvicorn tour_guide.main:app --reload
```

### 2. Flutter App（Android Emulator）

```bash
cd flutter_app
# 設定 Android Maps API Key
echo "MAPS_API_KEY_ANDROID=YOUR_KEY" >> android/local.properties

flutter run --dart-define-from-file=dart_defines/dev.json
```

### 3. Flutter App（iOS Simulator）

```bash
cd flutter_app
# 設定 iOS Maps API Key
cp ios/Flutter/LocalConfig.xcconfig.example ios/Flutter/LocalConfig.xcconfig
# 編輯 LocalConfig.xcconfig 填入 MAPS_API_KEY_IOS

flutter run \
  --dart-define=BACKEND_URL=http://localhost:8000 \
  --dart-define=API_KEY=dev
```

## API Key 取得

| Key | 取得位置 |
|---|---|
| Gemini API Key | https://aistudio.google.com/apikey |
| Google Maps API Key（Android） | GCP Console → APIs → Maps SDK for Android |
| Google Maps API Key（iOS） | GCP Console → APIs → Maps SDK for iOS |
| Google Places API Key | GCP Console → APIs → Places API |

## GCP 設定與部署

```bash
# 1. 建立 GCP 專案（僅需執行一次）
scripts/setup-gcp.sh

# 2. 部署後端
export GEMINI_API_KEY=your-gemini-key
export GOOGLE_PLACES_API_KEY=your-places-key
scripts/deploy-backend.sh

# 3. 設定 Flutter prod dart-define
cp flutter_app/dart_defines/prod.json.example flutter_app/dart_defines/prod.json
# 編輯 prod.json 填入 BACKEND_URL 和 API_KEY

# 4. 跑 prod Flutter
cd flutter_app
flutter run --dart-define-from-file=dart_defines/prod.json
```

## 測試

```bash
# 後端
cd backend && .venv/bin/pytest -v

# Flutter
cd flutter_app && flutter test

# Flutter 靜態分析
cd flutter_app && flutter analyze
```
```

- [ ] **Step 3: Commit**

```bash
git add flutter_app/dart_defines/prod.json.example SETUP.md
git commit -m "docs: add prod.json.example and SETUP.md for complete setup guide"
```

---

## 完成驗收

執行以下確認 Plan F 實作完整：

- [ ] `cd backend && .venv/bin/pytest -v` — 195+ tests PASS
- [ ] `cd flutter_app && flutter test` — 78+ tests PASS  
- [ ] `cd flutter_app && flutter analyze` — 無 error/warning
- [ ] Android 真機：`flutter run --dart-define-from-file=dart_defines/dev.json` → 鎖屏 → 走近 POI → 收到本地通知
- [ ] iOS 真機：同上
- [ ] `curl https://<cloud-run-url>/health` → `{"status":"ok"}`
- [ ] `curl -H "X-Api-Key: wrong" https://<cloud-run-url>/poi/nearby?...` → HTTP 401
- [ ] `curl -H "X-Api-Key: <correct>" https://<cloud-run-url>/poi/nearby?lat=25.1&lon=121.5&radius=500&lang=zh-TW&persona=history_uncle` → HTTP 200

---

## Spec 對照表（自我審查）

| Spec 需求 | 對應 Task |
|---|---|
| geolocator AndroidSettings + AppleSettings | Task 6 |
| NotificationService（Fake + Real） | Task 4 |
| appLifecycleStateProvider | Task 5 |
| TriggerNotifier 背景路由 | Task 8 |
| HomeScreen always 權限提示 | Task 9 |
| App lifecycle observer + NotificationService.init() | Task 10 |
| Android manifest permissions + foreground service | Task 11 |
| iOS Info.plist + AppDelegate + xcconfig | Task 12 |
| Dockerfile + .dockerignore | Task 2 |
| X-Api-Key config + middleware | Task 1 |
| X-Api-Key header in BackendClient | Task 7 |
| setup-gcp.sh + deploy-backend.sh | Task 14 |
| prod.json.example + .gitignore | Task 13 |
| SETUP.md | Task 15 |
