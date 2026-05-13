## ADDED Requirements

### Requirement: PersonaInfo model and kPersonas constants
The Flutter app SHALL define a `PersonaInfo` class with fields `id`, `emoji`, `displayName`, and `description`, and a `kPersonas` constant list containing exactly 5 entries matching the 5 backend persona IDs.

#### Scenario: kPersonas contains all 5 personas
- **WHEN** `kPersonas` is accessed at runtime
- **THEN** it SHALL contain exactly 5 `PersonaInfo` entries
- **THEN** the persona IDs SHALL be `history_uncle`, `story_brother`, `gossip_auntie`, `kid_sister`, `foodie` (in this order)

#### Scenario: Each PersonaInfo has required fields
- **WHEN** any entry in `kPersonas` is inspected
- **THEN** `id`, `emoji`, `displayName`, and `description` SHALL all be non-empty strings

### Requirement: SessionState persists persona and lang selections
The `SessionState` class SHALL include `persona` (default `'history_uncle'`) and `lang` (default `'zh-TW'`) fields, exposed via `copyWith()`.

#### Scenario: Default SessionState has expected persona and lang
- **WHEN** a new `SessionNotifier` is created
- **THEN** `state.persona` SHALL equal `'history_uncle'`
- **THEN** `state.lang` SHALL equal `'zh-TW'`

#### Scenario: copyWith() updates persona field
- **WHEN** `state.copyWith(persona: 'gossip_auntie')` is called
- **THEN** the returned state SHALL have `persona == 'gossip_auntie'`
- **THEN** all other fields SHALL remain unchanged

#### Scenario: copyWith() updates lang field
- **WHEN** `state.copyWith(lang: 'en')` is called
- **THEN** the returned state SHALL have `lang == 'en'`
- **THEN** all other fields SHALL remain unchanged

### Requirement: SessionNotifier.setPersona() and setLang() only work when idle
The `SessionNotifier` SHALL expose `setPersona(String persona)` and `setLang(String lang)` methods that update `SessionState` only when `status == SessionStatus.idle`.

#### Scenario: setPersona() updates state when idle
- **WHEN** `SessionNotifier.setPersona('story_brother')` is called while `status == idle`
- **THEN** `state.persona` SHALL become `'story_brother'`

#### Scenario: setPersona() is no-op when session is active
- **WHEN** `SessionNotifier.setPersona('story_brother')` is called while `status != idle`
- **THEN** `state.persona` SHALL remain unchanged

#### Scenario: setLang() updates state when idle
- **WHEN** `SessionNotifier.setLang('en')` is called while `status == idle`
- **THEN** `state.lang` SHALL become `'en'`

#### Scenario: setLang() is no-op when session is active
- **WHEN** `SessionNotifier.setLang('en')` is called while `status != idle`
- **THEN** `state.lang` SHALL remain unchanged

### Requirement: PersonaSelector displays 5 vertical persona cards
The `PersonaSelector` widget SHALL render 5 vertical cards, each displaying the persona's emoji, displayName, and description, with a highlighted border and check icon for the currently selected persona.

#### Scenario: All 5 persona names are visible
- **WHEN** `PersonaSelector` is rendered
- **THEN** all 5 persona `displayName` values SHALL be visible on screen

#### Scenario: All 5 persona emojis are visible
- **WHEN** `PersonaSelector` is rendered
- **THEN** all 5 persona `emoji` values SHALL be visible on screen

#### Scenario: Default selected persona shows check icon
- **WHEN** `PersonaSelector` is rendered with default SessionState
- **THEN** exactly one `Icons.check_circle` icon SHALL be visible (for `history_uncle`)

#### Scenario: Tapping a persona card updates selection
- **WHEN** user taps the card for `'故事大哥哥'`
- **THEN** `sessionProvider.notifier.setPersona('story_brother')` SHALL be called
- **THEN** `Icons.check_circle` SHALL move to the tapped card
- **THEN** exactly one `Icons.check_circle` icon SHALL be visible

### Requirement: HomeScreen shows PersonaSelector and language SegmentedButton
The `HomeScreen` SHALL include a `SegmentedButton<String>` for language selection (options: `'zh-TW'` / `'en'`) and the `PersonaSelector` widget in a scrollable layout.

#### Scenario: HomeScreen displays language toggle
- **WHEN** `HomeScreen` is rendered
- **THEN** a `SegmentedButton` with labels `'中文'` and `'EN'` SHALL be visible

#### Scenario: HomeScreen displays all 5 persona cards
- **WHEN** `HomeScreen` is rendered
- **THEN** all 5 persona display names SHALL be visible (via `PersonaSelector`)

#### Scenario: Language toggle calls setLang with correct value
- **WHEN** user taps `'EN'` in the `SegmentedButton`
- **THEN** `sessionProvider.notifier.setLang('en')` SHALL be called

#### Scenario: Language toggle is disabled while session is starting
- **WHEN** `session.status == SessionStatus.starting`
- **THEN** the `SegmentedButton.onSelectionChanged` SHALL be `null` (disabled)

#### Scenario: HomeScreen is scrollable
- **WHEN** `HomeScreen` is rendered on a small screen
- **THEN** the content SHALL be wrapped in a `SingleChildScrollView` to prevent overflow
