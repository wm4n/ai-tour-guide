## MODIFIED Requirements

### Requirement: HomeScreen displays persona and start button
The HomeScreen SHALL display the app name, current persona chip, and an 「開始旅程」 button. The displayed persona chips SHALL reflect the updated `kPersonas` list which includes `defaultTriggerRadiusM` for each persona.

#### Scenario: Idle state shows enabled button
- **WHEN** session status is `idle`
- **THEN** 「開始旅程」 button is enabled and persona chip shows the selected persona's display name

#### Scenario: Starting state shows loading indicator
- **WHEN** session status is `starting`
- **THEN** button shows a circular progress indicator and is disabled

---

## ADDED Requirements

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
