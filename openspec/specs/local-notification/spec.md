# Capability: Local Notifications

## Purpose

Displays local notifications to alert users about nearby POIs, particularly when the app is in the background or not actively engaged.

---

## Requirements

### Requirement: NotificationService abstract interface
The system SHALL define an `abstract class NotificationService` with two methods: `Future<void> init()` and `Future<void> showPoiTrigger(Poi poi)`. A `FakeNotificationService` SHALL record all calls for test verification. A `RealNotificationService` SHALL wrap `flutter_local_notifications`.

#### Scenario: FakeNotificationService records init call
- **WHEN** `FakeNotificationService.init()` is called
- **THEN** `fakeService.initCalled == true`

#### Scenario: FakeNotificationService records showPoiTrigger call
- **WHEN** `FakeNotificationService.showPoiTrigger(poi)` is called
- **THEN** `fakeService.shownPois` contains the poi

#### Scenario: RealNotificationService initialises flutter_local_notifications
- **WHEN** `RealNotificationService.init()` is called
- **THEN** `FlutterLocalNotificationsPlugin.initialize()` is called with Android and iOS init settings

---

### Requirement: notificationServiceProvider and appLifecycleStateProvider in providers.dart
The `providers.dart` SHALL expose `notificationServiceProvider` (returns `NotificationService`) and `appLifecycleStateProvider` (a `StateProvider<AppLifecycleState>` initialised to `AppLifecycleState.resumed`). In production, `notificationServiceProvider` returns `RealNotificationService`; in tests, it is overridden with `FakeNotificationService`.

#### Scenario: notificationServiceProvider returns NotificationService instance
- **WHEN** `container.read(notificationServiceProvider)` is called in production
- **THEN** it returns a `RealNotificationService` instance

#### Scenario: appLifecycleStateProvider initialised to resumed
- **WHEN** `container.read(appLifecycleStateProvider)` is called at app start
- **THEN** the value is `AppLifecycleState.resumed`

---

### Requirement: App widget initialises NotificationService and tracks lifecycle
The `App` widget SHALL be a `ConsumerStatefulWidget` implementing `WidgetsBindingObserver`. On `initState`, it SHALL call `NotificationService.init()` and register itself with `WidgetsBinding`. On `didChangeAppLifecycleState`, it SHALL update `appLifecycleStateProvider`.

#### Scenario: NotificationService.init called on app start
- **WHEN** `App` widget is mounted
- **THEN** `notificationService.init()` is awaited during `initState`

#### Scenario: appLifecycleStateProvider updated on lifecycle change
- **WHEN** app transitions to `paused`
- **THEN** `appLifecycleStateProvider` state becomes `AppLifecycleState.paused`

---

### Requirement: POI arrival notification shows title and body
The `showPoiTrigger` SHALL display a local notification with the POI name as title and a fixed body string (e.g. 「你到達了一個景點！」).

#### Scenario: Notification shows POI name
- **WHEN** `RealNotificationService.showPoiTrigger(poi)` is called
- **THEN** the notification title equals `poi.name`

#### Scenario: Notification has fixed body text
- **WHEN** `RealNotificationService.showPoiTrigger(poi)` is called
- **THEN** the notification body is `"你到達了一個景點！"`
