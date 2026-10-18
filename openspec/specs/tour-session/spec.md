# Capability: Tour Session

## Purpose

Manages the lifecycle of a tour journey session, including state transitions, UI entry point (HomeScreen), and location permission handling.

---

## Requirements

### Requirement: Session lifecycle management
The app SHALL maintain a session state machine with four states: `idle`, `starting`, `active`, `ending`. Starting a journey on Android enables tour-mode playback delivery for background-capable triggers once required foreground location access is granted. Stopping a journey SHALL transition to `ending`, stop location updates, clear the tour playback queue, stop active narration and media playback state, record `ended_at`, and return the session to `idle`.

#### Scenario: Start session with permission granted
- **WHEN** the user taps the start-journey action and required location permission is granted
- **THEN** the session transitions `idle -> starting -> active` and journey playback delivery becomes eligible

#### Scenario: Start session with permission denied
- **WHEN** the user taps the start-journey action and location permission is denied
- **THEN** the session returns to `idle` and the app shows permission guidance instead of activating the journey

#### Scenario: Stop session clears queue and playback state
- **WHEN** the user stops the active journey
- **THEN** the session transitions to `ending`, location updates stop, the tour playback queue is cleared, active narration/media playback stops, `ended_at` is recorded, and the session returns to `idle`

---

### Requirement: HomeScreen displays persona and start button
The HomeScreen SHALL display the app name, current persona chip, and an 「開始旅程」 button. The displayed persona chips SHALL reflect the updated `kPersonas` list which includes `defaultTriggerRadiusM` for each persona.

#### Scenario: Idle state shows enabled button
- **WHEN** session status is `idle`
- **THEN** 「開始旅程」 button is enabled and persona chip shows the selected persona's display name

#### Scenario: Starting state shows loading indicator
- **WHEN** session status is `starting`
- **THEN** button shows a circular progress indicator and is disabled

---

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

---

### Requirement: PersonaInfo includes default trigger radius
The `PersonaInfo` class SHALL include a `defaultTriggerRadiusM: int` field. The `kPersonas` constant SHALL be updated with the following values: `foodie: 50`, all other personas (`history_uncle`, `story_brother`, `gossip_auntie`, `kid_sister`): `100`.

#### Scenario: Foodie persona has 50m radius
- **WHEN** `kPersonas.firstWhere((p) => p.id == 'foodie')` is evaluated
- **THEN** `persona.defaultTriggerRadiusM == 50`

#### Scenario: History uncle has 100m radius
- **WHEN** `kPersonas.firstWhere((p) => p.id == 'history_uncle')` is evaluated
- **THEN** `persona.defaultTriggerRadiusM == 100`

#### Scenario: All non-foodie personas have 100m radius
- **WHEN** each of `story_brother`, `gossip_auntie`, `kid_sister` personas is retrieved from `kPersonas`
- **THEN** each has `defaultTriggerRadiusM == 100`

---

### Requirement: PersonaConfig and foodie.yaml support default_trigger_radius_m
The backend `PersonaConfig` dataclass SHALL include `default_trigger_radius_m: int = 100`. The `PersonaLoader._parse()` SHALL read `default_trigger_radius_m` from YAML, defaulting to 100 if absent. The `foodie.yaml` SHALL set `poi_source: google_places` and `default_trigger_radius_m: 50`.

#### Scenario: foodie.yaml parsed with 50m radius
- **WHEN** `PersonaLoader` loads `foodie.yaml`
- **THEN** `config.default_trigger_radius_m == 50` and `config.poi_source == "google_places"`

#### Scenario: YAML without radius defaults to 100
- **WHEN** a persona YAML does not include `default_trigger_radius_m`
- **THEN** `PersonaConfig.default_trigger_radius_m == 100`
