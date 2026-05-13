## ADDED Requirements

### Requirement: Persona YAML registry covers all 5 personas
The system SHALL provide YAML definition files for all 5 personas (`history_uncle`, `story_brother`, `gossip_auntie`, `kid_sister`, `foodie`), each containing bilingual (zh-TW / en) `system_prompt`, `narration_template`, `qa_template`, `voice`, and `voice_style` fields.

#### Scenario: All persona YAMLs load without error
- **WHEN** `PersonaLoader.load_all()` is called with the default personas directory
- **THEN** all 5 persona IDs (`history_uncle`, `story_brother`, `gossip_auntie`, `kid_sister`, `foodie`) SHALL be present in the returned registry dict
- **THEN** each `PersonaConfig` object SHALL have `system_prompt` with both `zh-TW` and `en` keys
- **THEN** each `PersonaConfig` object SHALL have `narration_template` with both `zh-TW` and `en` keys

#### Scenario: Persona YAML id matches filename
- **WHEN** a persona YAML file named `<persona_id>.yaml` is loaded
- **THEN** the `id` field in the YAML SHALL equal `<persona_id>`

### Requirement: PersonaLoader.load_all() classmethod
The `PersonaLoader` class SHALL provide a `load_all(base_dir)` classmethod that loads all `.yaml` files from the given directory and returns a `dict[str, PersonaConfig]` keyed by persona id.

#### Scenario: load_all() with default directory
- **WHEN** `PersonaLoader.load_all()` is called without arguments
- **THEN** it SHALL use the production personas directory (`backend/prompts/personas/`)
- **THEN** it SHALL return a non-empty dict containing all available persona configs

#### Scenario: load_all() with empty directory
- **WHEN** `PersonaLoader.load_all(base_dir=<empty_tmp_dir>)` is called
- **THEN** it SHALL return an empty dict `{}`

#### Scenario: load_all() with custom directory containing one YAML
- **WHEN** `PersonaLoader.load_all(base_dir=<dir_with_one_yaml>)` is called
- **THEN** it SHALL return a dict with exactly 1 entry matching the YAML's id field

### Requirement: Persona registry loaded at FastAPI startup
The FastAPI application SHALL load all persona configs into memory during startup (via `create_app()`), before serving any requests, and inject the registry into the `/narration` endpoint via dependency injection.

#### Scenario: Application starts with persona registry populated
- **WHEN** `create_app()` is called
- **THEN** `PersonaLoader.load_all()` SHALL be called once
- **THEN** the resulting registry SHALL be injected into the `narration.get_persona_registry` dependency override

### Requirement: Unknown persona ID returns HTTP 400
The `/narration` endpoint SHALL validate the `persona` field against the loaded registry and return `HTTP 400` with an informative error message if the persona is not found.

#### Scenario: Valid persona ID returns 200
- **WHEN** `POST /narration` is called with a `persona` field matching a registered persona ID
- **THEN** the endpoint SHALL proceed with narration generation and return `HTTP 200` (SSE stream)

#### Scenario: Unknown persona ID returns 400
- **WHEN** `POST /narration` is called with `persona="unknown_persona"`
- **THEN** the endpoint SHALL return `HTTP 400`
- **THEN** the response `detail` field SHALL mention the invalid persona ID

#### Scenario: Persona registry injectable in tests
- **WHEN** a test overrides `get_persona_registry` with a fake registry dict
- **THEN** the endpoint SHALL use the fake registry for validation
- **THEN** an unknown persona (not in fake registry) SHALL return `HTTP 400`
