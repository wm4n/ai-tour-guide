## MODIFIED Requirements

### Requirement: SSE stream parsing
The app SHALL parse `POST /narration` SSE responses into typed events: `meta`, `text`, `audio`, `end`, `error`. The `MetaEvent` SHALL include a `poiName` field (string, defaults to empty string) parsed from `poi_name` in the SSE JSON data.

#### Scenario: Parse meta event with poi_name
- **WHEN** SSE stream emits `event: meta` with `data: {"poi_id":"...","poi_name":"故宮博物院","confidence":"high",...}`
- **THEN** SseParser yields a `MetaEvent` with `poiName == "故宮博物院"`

#### Scenario: Parse meta event without poi_name (backward compat)
- **WHEN** SSE stream emits `event: meta` without `poi_name` field
- **THEN** SseParser yields a `MetaEvent` with `poiName == ""`

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

#### Scenario: Partial chunk boundary
- **WHEN** a TCP packet splits an SSE block in the middle
- **THEN** SseParser buffers partial data and only yields the event after the complete `\n\n` delimiter is received

---

## ADDED Requirements

### Requirement: Multi-candidate narrate() API in BackendClient
The `BackendClient.narrate()` method SHALL accept `List<POI> candidates` and optional `PreviousSelection? previousSelection` instead of a single POI. The client SHALL serialize all candidates into the `candidates` JSON array.

#### Scenario: narrate() serializes all candidates
- **WHEN** `BackendClient.narrate()` is called with a list of 5 POIs
- **THEN** the HTTP request body SHALL contain `candidates` array with all 5 POI entries

#### Scenario: narrate() includes previous_selection when provided
- **WHEN** `PreviousSelection` with `poiId`, `poiName`, and `script` is passed
- **THEN** request body SHALL include `previous_selection` object with all three fields

#### Scenario: narrate() omits previous_selection when null
- **WHEN** `previousSelection` is null
- **THEN** request body SHALL NOT include `previous_selection` key

---

### Requirement: Script accumulation in NarrationNotifier
`NarrationState` SHALL include a `scriptBuffer` field that accumulates all `TextEvent` chunks during a narration session. The buffer SHALL reset to empty string at the start of each new `narrate()` call.

#### Scenario: scriptBuffer accumulates text chunks
- **WHEN** three `TextEvent`s with chunks "A", "B", "C" are received in sequence
- **THEN** `NarrationState.scriptBuffer` equals "ABC" after the third event

#### Scenario: scriptBuffer resets on new narrate() call
- **WHEN** `NarrationNotifier.narrate()` is called for a second time
- **THEN** `scriptBuffer` is reset to empty string before streaming starts

---

### Requirement: NarrationNotifier resolves POI from MetaEvent
`NarrationNotifier` SHALL resolve the played POI by matching `MetaEvent.poiId` against the candidates list. If no match is found, it SHALL fall back to `candidates.first`.

#### Scenario: POI resolved from MetaEvent poi_id
- **WHEN** MetaEvent arrives with `poi_id` matching a candidate in the list
- **THEN** `NarrationState.currentPoi` is set to the matched candidate

#### Scenario: Fallback to first candidate on unmatched poi_id
- **WHEN** MetaEvent `poi_id` does not match any candidate
- **THEN** `NarrationState.currentPoi` is set to `candidates.first`
