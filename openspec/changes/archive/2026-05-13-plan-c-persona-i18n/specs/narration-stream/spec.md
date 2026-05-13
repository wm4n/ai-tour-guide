## MODIFIED Requirements

### Requirement: narrate() accepts dynamic persona and lang parameters
The `NarrationNotifier.narrate()` method SHALL accept `{required String persona, required String lang}` as named parameters, and SHALL pass these values directly to the backend client call and to the local DB record. The method SHALL NOT hardcode persona or lang values internally.

#### Scenario: narrate() passes persona and lang to backend client
- **WHEN** `narrationNotifier.narrate(poi, persona: 'gossip_auntie', lang: 'en')` is called
- **THEN** `BackendClient.narrate()` SHALL be called with `persona: 'gossip_auntie'` and `lang: 'en'`

#### Scenario: narrate() records correct persona and lang to DB
- **WHEN** a narration completes (EndEvent received) after being called with `persona: 'kid_sister'` and `lang: 'zh-TW'`
- **THEN** `LocalDb.recordNarration()` SHALL be called with `persona: 'kid_sister'` and `lang: 'zh-TW'`

#### Scenario: Calling narrate() without named parameters is a compile error
- **WHEN** `narrate(poi)` is called without `persona` and `lang` named parameters
- **THEN** the Dart compiler SHALL report a compile-time error (named params are required)

### Requirement: TriggerNotifier reads persona and lang from sessionProvider before narrating
The `TriggerNotifier` SHALL read the current `sessionProvider` state to obtain `persona` and `lang` values and pass them to `narrationNotifier.narrate()` when triggering a narration.

#### Scenario: TriggerNotifier passes session persona to narration
- **WHEN** a POI enters trigger range and `sessionProvider.state.persona == 'foodie'`
- **THEN** `narrationNotifier.narrate()` SHALL be called with `persona: 'foodie'`

#### Scenario: TriggerNotifier passes session lang to narration
- **WHEN** a POI enters trigger range and `sessionProvider.state.lang == 'en'`
- **THEN** `narrationNotifier.narrate()` SHALL be called with `lang: 'en'`
