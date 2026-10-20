## MODIFIED Requirements

### Requirement: Session lifecycle management
The app SHALL maintain a session state machine with four states: `idle`, `starting`, `active`, and `ending`. Starting a journey on Android enables tour-mode playback delivery for background-capable triggers once required foreground location access is granted. Stopping a journey SHALL transition to `ending`, stop location updates, clear the tour playback queue, stop active narration and media playback state, record `ended_at`, and return the session to `idle`.

#### Scenario: Start session with permission granted
- **WHEN** the user taps the start-journey action and required location permission is granted
- **THEN** the session transitions `idle -> starting -> active` and journey playback delivery becomes eligible

#### Scenario: Start session with permission denied
- **WHEN** the user taps the start-journey action and location permission is denied
- **THEN** the session returns to `idle` and the app shows permission guidance instead of activating the journey

#### Scenario: Stop session clears queue and playback state
- **WHEN** the user stops the active journey
- **THEN** the session transitions to `ending`, location updates stop, the tour playback queue is cleared, active narration/media playback stops, `ended_at` is recorded, and the session returns to `idle`

### Requirement: Location permission request on journey start
The app SHALL request foreground location permission before activating a session. After permission is granted, the journey start flow SHALL check whether background travel guidance is degraded. If location access is only `whileInUse`, the app SHALL explain that "Always Allow" is recommended for background tour playback. If notification permission is unavailable, the app SHALL warn that background notifications and media controls will be limited.

#### Scenario: Permission not yet granted
- **WHEN** the user starts a journey for the first time
- **THEN** the system location permission dialog is shown before the session can become active

#### Scenario: Permission permanently denied
- **WHEN** location permission is permanently denied
- **THEN** the app shows guidance to open system settings instead of activating the journey

#### Scenario: While-in-use permission shows background guidance
- **WHEN** the permission check returns `whileInUse` during journey start
- **THEN** the app shows guidance that background playback works best with "Always Allow" location access

#### Scenario: Missing notification permission shows a visibility warning
- **WHEN** notification permission is unavailable at journey start
- **THEN** the app warns that background trigger notifications and media controls may not be visible until notifications are enabled
