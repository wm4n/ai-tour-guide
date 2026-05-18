# Capability: Background Location Tracking

## Purpose

Enables continuous GPS position tracking even when the app is not in the foreground, using platform-specific background location APIs and permissions.

---

## Requirements

### Requirement: Background location updates via platform-specific settings
The `RealLocationService.start()` SHALL inject platform-specific `LocationSettings` to enable background GPS updates. On Android it SHALL use `AndroidSettings` with `ForegroundNotificationConfig`; on iOS it SHALL use `AppleSettings` with `allowBackgroundLocationUpdates: true`.

#### Scenario: Android background location starts foreground service
- **WHEN** `RealLocationService.start()` is called on Android
- **THEN** `AndroidSettings` is constructed with a `ForegroundNotificationConfig` and passed to `Geolocator.getPositionStream()`

#### Scenario: iOS background location allows background updates
- **WHEN** `RealLocationService.start()` is called on iOS
- **THEN** `AppleSettings` with `allowBackgroundLocationUpdates: true` and `activityType: ActivityType.fitness` is passed to `Geolocator.getPositionStream()`

#### Scenario: Background location continues after screen lock
- **WHEN** device screen is locked while session is active
- **THEN** position stream continues to emit updates and `TriggerNotifier` evaluates new positions

---

### Requirement: Location permission check for background guidance
The `LocationService` abstract class SHALL expose `checkPermission()` that returns the current `LocationPermission` without requesting it. The `RealLocationService` SHALL implement this by calling `Geolocator.checkPermission()`.

#### Scenario: checkPermission returns current grant level
- **WHEN** `RealLocationService.checkPermission()` is called
- **THEN** it returns the current `LocationPermission` value without showing a system dialog

#### Scenario: FakeLocationService checkPermission returns whileInUse by default
- **WHEN** `FakeLocationService.checkPermission()` is called with no setup
- **THEN** it returns `LocationPermission.whileInUse`

---

### Requirement: Android manifest declares background location permissions
The `AndroidManifest.xml` SHALL declare `ACCESS_BACKGROUND_LOCATION`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`, and `POST_NOTIFICATIONS` permissions. It SHALL also declare the `GeolocatorService` with `foregroundServiceType="location"`.

#### Scenario: Background location permission declared
- **WHEN** Android system reads the manifest
- **THEN** `uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION"` is present

#### Scenario: GeolocatorService declared with foreground type
- **WHEN** Android system reads the manifest
- **THEN** `service android:name="com.baseflow.geolocator.GeolocatorService"` has `android:foregroundServiceType="location"`

---

### Requirement: iOS Info.plist declares background location mode
The `Info.plist` SHALL include `UIBackgroundModes: [location]` and three `NSLocation*UsageDescription` keys with Traditional Chinese descriptions.

#### Scenario: UIBackgroundModes contains location
- **WHEN** iOS system reads Info.plist
- **THEN** `UIBackgroundModes` array contains `"location"`

#### Scenario: All location usage descriptions present
- **WHEN** iOS system reads Info.plist
- **THEN** `NSLocationWhenInUseUsageDescription`, `NSLocationAlwaysUsageDescription`, and `NSLocationAlwaysAndWhenInUseUsageDescription` are all present
