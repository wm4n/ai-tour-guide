## MODIFIED Requirements

### Requirement: SSE stream parsing
The app SHALL parse `POST /narration` SSE responses into typed events: `meta`, `text`, `audio`, `end`, `error`, `skip`. The `MetaEvent` SHALL include a `poiName` field (string, defaults to empty string) parsed from `poi_name` in the SSE JSON data. The `SkipEvent` SHALL carry a `minDisplacementM` field parsed from `min_displacement_m` (defaults to 1500.0).

#### Scenario: Parse meta event with poi_name
- **WHEN** SSE stream emits `event: meta` with `data: {"poi_id":"...","poi_name":"故宮博物院","confidence":"high",...}`
- **THEN** SseParser yields a `MetaEvent` with `poiName == "故宮博物院"`

#### Scenario: Parse meta event without poi_name (backward compat)
- **WHEN** SSE stream emits `event: meta` without `poi_name` field
- **THEN** SseParser yields a `MetaEvent` with `poiName == ""`

#### Scenario: Parse meta event
- **WHEN** SSE stream emits `event: meta` with `data: {"poi_id":"...","confidence":"high",...}`
- **THEN** SseParser yields a `MetaEvent` with the parsed fields

#### Scenario: Parse text event
- **WHEN** SSE stream emits `event: text` with `data: {"chunk":"..."}`
- **THEN** SseParser yields a `TextEvent` with the text chunk

#### Scenario: Parse audio event
- **WHEN** SSE stream emits `event: audio` with `data: {"chunk_b64":"...","sentence_idx":0}`
- **THEN** SseParser yields an `AudioEvent` with the base64 string and index

#### Scenario: Parse end event
- **WHEN** SSE stream emits `event: end`
- **THEN** SseParser yields an `EndEvent`

#### Scenario: Parse error event
- **WHEN** SSE stream emits `event: error` with `data: {"code":"RATE_LIMITED","retry_after_s":30}`
- **THEN** SseParser yields an `ErrorEvent` with code and retry duration

#### Scenario: Parse skip event with min_displacement_m
- **WHEN** SSE stream emits `event: skip` with `data: {"min_displacement_m": 1500.0}`
- **THEN** SseParser yields a `SkipEvent` with `minDisplacementM == 1500.0`

#### Scenario: Parse skip event without min_displacement_m (backward compat)
- **WHEN** SSE stream emits `event: skip` without `min_displacement_m` field
- **THEN** SseParser yields a `SkipEvent` with `minDisplacementM == 1500.0` (default)

#### Scenario: Unknown event type silently dropped
- **WHEN** SSE stream emits an event with an unrecognized type
- **THEN** SseParser silently discards the event and continues streaming

#### Scenario: Partial chunk boundary
- **WHEN** a TCP packet splits an SSE block in the middle
- **THEN** SseParser buffers partial data and only yields the event after the complete `\n\n` delimiter is received

## ADDED Requirements

### Requirement: NarrationNotifier handles SkipEvent
`NarrationNotifier` SHALL process `SkipEvent` by setting `NarrationState.lastEventWasSkip = true` and maintaining `NarrationStatus.idle`. This flag signals `TriggerNotifier` to enter displacement-wait mode instead of starting a countdown.

#### Scenario: SkipEvent sets lastEventWasSkip flag
- **WHEN** `NarrationNotifier` receives a `SkipEvent` from the SSE stream
- **THEN** `NarrationState.lastEventWasSkip` is set to `true` and `status` remains `idle`

#### Scenario: lastEventWasSkip cleared on next narrate() call
- **WHEN** `NarrationNotifier.narrate()` is called again after a skip
- **THEN** `NarrationState.lastEventWasSkip` is reset to `false` at the start of the call
