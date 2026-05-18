## ADDED Requirements

### Requirement: Android Maps API Key injected via local.properties
The `build.gradle.kts` SHALL read `MAPS_API_KEY` from `local.properties` and inject it into `AndroidManifest.xml` via `manifestPlaceholders`. The `local.properties` file SHALL NOT be committed to git.

#### Scenario: build.gradle.kts reads MAPS_API_KEY from local.properties
- **WHEN** `local.properties` contains `MAPS_API_KEY=abc123`
- **THEN** `android { defaultConfig { manifestPlaceholders["MAPS_API_KEY"] = "abc123" } }` is applied

#### Scenario: AndroidManifest.xml references placeholder
- **WHEN** Android app builds with `MAPS_API_KEY` in `local.properties`
- **THEN** the Google Maps meta-data entry uses `${MAPS_API_KEY}` placeholder syntax

#### Scenario: local.properties is gitignored
- **WHEN** `.gitignore` is checked
- **THEN** `local.properties` is listed (already standard Android gitignore)

---

### Requirement: iOS Maps API Key injected via LocalConfig.xcconfig
The `Debug.xcconfig` and `Release.xcconfig` SHALL include `#include? "LocalConfig.xcconfig"` to optionally load a local override. `AppDelegate.swift` SHALL read the Maps API Key from `Bundle.main.infoDictionary["MAPS_API_KEY_IOS"]` instead of using a hardcoded string. A `LocalConfig.xcconfig.example` SHALL be committed to guide setup.

#### Scenario: AppDelegate reads MAPS_API_KEY_IOS from bundle
- **WHEN** `LocalConfig.xcconfig` defines `MAPS_API_KEY_IOS = abc123`
- **THEN** `AppDelegate.swift` passes `abc123` to `GMSServices.provideAPIKey()`

#### Scenario: LocalConfig.xcconfig is gitignored
- **WHEN** `.gitignore` is checked
- **THEN** `ios/Flutter/LocalConfig.xcconfig` is listed

#### Scenario: LocalConfig.xcconfig.example is committed as template
- **WHEN** `flutter_app/ios/Flutter/LocalConfig.xcconfig.example` is read
- **THEN** it contains `MAPS_API_KEY_IOS = YOUR_MAPS_API_KEY_HERE` as a placeholder

---

### Requirement: dart_defines/prod.json contains BACKEND_URL and API_KEY
The `flutter_app/dart_defines/prod.json` SHALL store production values for `BACKEND_URL` and `API_KEY`. A `prod.json.example` SHALL be committed showing the expected keys. `prod.json` SHALL be gitignored.

#### Scenario: prod.json.example shows expected structure
- **WHEN** `flutter_app/dart_defines/prod.json.example` is read
- **THEN** it contains both `BACKEND_URL` and `API_KEY` keys with placeholder values

#### Scenario: prod.json is gitignored
- **WHEN** `.gitignore` is checked
- **THEN** `flutter_app/dart_defines/prod.json` is listed
