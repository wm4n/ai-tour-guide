# Capability: Tour Session

## Purpose

Manages the lifecycle of a tour journey session, including state transitions, UI entry point (HomeScreen), and location permission handling.

---

## Requirements

### Requirement: Session lifecycle management
The app SHALL maintain a session state machine with four states: `idle`, `starting`, `active`, `ending`.

#### Scenario: Start session with permission granted
- **WHEN** user taps 「開始旅程」 and location permission is granted
- **THEN** session transitions `idle → starting → active` and app navigates to MapScreen

#### Scenario: Start session with permission denied
- **WHEN** user taps 「開始旅程」 and location permission is denied
- **THEN** session returns to `idle` and HomeScreen shows a permission guidance dialog

#### Scenario: Stop session
- **WHEN** user taps 「結束」 on MapScreen
- **THEN** session transitions to `ending`, LocationService stops, DB records `ended_at`, session becomes `idle`

---

### Requirement: HomeScreen displays persona and start button
The HomeScreen SHALL display the app name, current persona chip (`歷史大叔`), and an 「開始旅程」 button.

#### Scenario: Idle state shows enabled button
- **WHEN** session status is `idle`
- **THEN** 「開始旅程」 button is enabled and persona chip shows `歷史大叔`

#### Scenario: Starting state shows loading indicator
- **WHEN** session status is `starting`
- **THEN** button shows a circular progress indicator and is disabled

---

### Requirement: Location permission request on journey start
The app SHALL request foreground location permission before activating a session.

#### Scenario: Permission not yet granted
- **WHEN** session starts for the first time
- **THEN** system permission dialog is shown to the user

#### Scenario: Permission permanently denied
- **WHEN** location permission is permanently denied
- **THEN** HomeScreen shows dialog with 「請在設定中允許定位權限」 message and a button to open system settings
