## ADDED Requirements

### Requirement: AppSettings model with persistent storage
The system SHALL provide an `AppSettings` model with `skipDisplacementM` (default 1500.0 m) and `countdownSeconds` (default 90 s) fields. Settings SHALL be persisted using SharedPreferences and loaded automatically on app start.

#### Scenario: Default values on first launch
- **WHEN** the app is launched for the first time with no persisted settings
- **THEN** `appSettingsProvider` returns `AppSettings(skipDisplacementM: 1500.0, countdownSeconds: 90)`

#### Scenario: Persisted values loaded on restart
- **WHEN** the app restarts after the user has changed settings
- **THEN** `appSettingsProvider` loads and returns the previously saved values from SharedPreferences

#### Scenario: setSkipDisplacement updates state and persists
- **WHEN** `AppSettingsNotifier.setSkipDisplacement(meters)` is called
- **THEN** `appSettingsProvider` state is updated immediately AND the value is written to SharedPreferences under key `skip_displacement_m`

#### Scenario: setCountdownSeconds updates state and persists
- **WHEN** `AppSettingsNotifier.setCountdownSeconds(seconds)` is called
- **THEN** `appSettingsProvider` state is updated immediately AND the value is written to SharedPreferences under key `countdown_seconds`

### Requirement: SettingsScreen UI for user configuration
The system SHALL provide a `SettingsScreen` accessible from the MapScreen AppBar. It SHALL allow users to adjust narration countdown interval (30–300 s) and skip displacement threshold (500–5000 m) via sliders.

#### Scenario: Settings screen is accessible from MapScreen
- **WHEN** the user taps the ⚙️ (settings) icon button in the MapScreen AppBar
- **THEN** the app navigates to `SettingsScreen`

#### Scenario: Countdown slider range and persistence
- **WHEN** the user moves the countdown slider on SettingsScreen
- **THEN** the displayed value updates in real-time and the change is persisted to SharedPreferences

#### Scenario: Displacement slider range and persistence
- **WHEN** the user moves the displacement threshold slider on SettingsScreen
- **THEN** the displayed value updates in real-time and the change is persisted to SharedPreferences
