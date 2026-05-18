## ADDED Requirements

### Requirement: PersonaConfig carries no_data_context fallback phrase
`PersonaConfig` SHALL include a `no_data_context: dict[str, str]` field (with `default_factory=dict` for backward compatibility) that holds a pre-written verbal fallback phrase per language. The persona YAML loader SHALL parse this field when present and default to an empty dict when absent.

#### Scenario: Persona YAML with no_data_context loads correctly
- **WHEN** a persona YAML includes a `no_data_context` block with `zh-TW` and `en` keys
- **THEN** `PersonaLoader.load_from_path()` returns a `PersonaConfig` with `no_data_context["zh-TW"]` and `no_data_context["en"]` set to those values

#### Scenario: Persona YAML without no_data_context defaults to empty dict
- **WHEN** a persona YAML does not include a `no_data_context` block
- **THEN** `PersonaConfig.no_data_context` equals `{}`

---

### Requirement: NarrationService short-circuits to TTS when wiki data is absent
`NarrationService.narrate()` SHALL, immediately after yielding the `MetaEvent` and before building the LLM prompt, check if `poi.wiki is None`. If so, and if `persona.no_data_context` contains an entry for the requested language, the service SHALL:
1. Yield a `TextEvent` with the `no_data_context` phrase
2. Synthesize the phrase to audio via TTS
3. Yield an `AudioEvent` with the base64-encoded audio
4. Yield an `EndEvent`
5. Return without calling the LLM

#### Scenario: No-data short-circuit skips LLM when wiki is None
- **WHEN** `NarrationService.narrate(poi, persona, lang, length)` is called with `poi.wiki == None` and `persona.no_data_context` contains the requested language
- **THEN** `LLMProvider.chat_stream()` is NOT called

#### Scenario: No-data short-circuit emits correct events
- **WHEN** the short-circuit fires for language `"zh-TW"` with `no_data_context["zh-TW"] == "這附近大哥哥也不太熟！"`
- **THEN** the event stream yields exactly: `MetaEvent`, `TextEvent(chunk="這附近大哥哥也不太熟！")`, `AudioEvent`, `EndEvent`

#### Scenario: Normal LLM path taken when wiki is present
- **WHEN** `poi.wiki` is a `WikiArticle` with non-empty extract
- **THEN** `LLMProvider.chat_stream()` IS called and no short-circuit occurs

#### Scenario: Short-circuit not triggered when no_data_context is empty
- **WHEN** `poi.wiki is None` but `persona.no_data_context` is `{}`
- **THEN** the service falls through to the LLM path (no short-circuit)

---

### Requirement: Persona narration templates include scene-opening instructions
Each of the five persona YAML files SHALL include a scene-opening instruction appended to the `narration_template` for each language. The instruction SHALL prohibit greetings and mandate scene-action sentence openings specific to each persona's voice and style.

#### Scenario: story_brother template prohibits greetings
- **WHEN** `PersonaLoader.load_from_path("story_brother.yaml")` is called
- **THEN** `persona.narration_template["zh-TW"]` contains the text `嚴禁任何問候語`

#### Scenario: history_uncle template requires historical sentence opening
- **WHEN** `PersonaLoader.load_from_path("history_uncle.yaml")` is called
- **THEN** `persona.narration_template["zh-TW"]` contains the text `直接進入歷史敘述`

#### Scenario: gossip_auntie template requires conspiratorial opening
- **WHEN** `PersonaLoader.load_from_path("gossip_auntie.yaml")` is called
- **THEN** `persona.narration_template["zh-TW"]` contains the text `小聲透露的語氣`

#### Scenario: kid_sister template requires curious observation opening
- **WHEN** `PersonaLoader.load_from_path("kid_sister.yaml")` is called
- **THEN** `persona.narration_template["zh-TW"]` contains the text `好奇的觀察句`

#### Scenario: foodie template requires sensory description opening
- **WHEN** `PersonaLoader.load_from_path("foodie.yaml")` is called
- **THEN** `persona.narration_template["zh-TW"]` contains the text `感官描述`
