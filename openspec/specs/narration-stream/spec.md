# Capability: Narration Stream

## Purpose

Handles real-time SSE streaming from the narration backend, FIFO audio chunk queuing and playback, subtitle display in the NarrationSheet, and graceful error handling.

---

## Requirements

### Requirement: SSE stream parsing
The app SHALL parse `POST /narration` SSE responses into typed events: `meta`, `text`, `audio`, `end`, `error`. The `MetaEvent` SHALL include a `poiName` field (string, defaults to empty string) parsed from `poi_name` in the SSE JSON data. The `MetaEvent` SHALL also include an `isNoData: bool` field (defaults to `false`) parsed from `is_no_data` in the SSE JSON data. The backend SHALL set `is_no_data: true` in the `MetaEvent` when the selected POI has no Wikipedia article.

#### Scenario: Parse meta event with poi_name
- **WHEN** SSE stream emits `event: meta` with `data: {"poi_id":"...","poi_name":"故宮博物院","confidence":"high",...}`
- **THEN** SseParser yields a `MetaEvent` with `poiName == "故宮博物院"`

#### Scenario: Parse meta event without poi_name (backward compat)
- **WHEN** SSE stream emits `event: meta` without `poi_name` field
- **THEN** SseParser yields a `MetaEvent` with `poiName == ""`

#### Scenario: Parse meta event
- **WHEN** SSE stream emits `event: meta` with `data: {"poi_id":"...","confidence":"high",...}`
- **THEN** SseParser yields a `MetaEvent` with the parsed fields

#### Scenario: Parse meta event with is_no_data true
- **WHEN** SSE stream emits `event: meta` with `data: {"poi_id":"...","is_no_data":true,...}`
- **THEN** SseParser yields a `MetaEvent` with `isNoData == true`

#### Scenario: Parse meta event without is_no_data (backward compat)
- **WHEN** SSE stream emits `event: meta` without `is_no_data` field
- **THEN** SseParser yields a `MetaEvent` with `isNoData == false`

#### Scenario: Backend sets is_no_data=true for wiki-less POI
- **WHEN** the narration service processes a POI with `wiki == None`
- **THEN** the emitted `MetaEvent` has `is_no_data: true`

#### Scenario: Backend sets is_no_data=false for POI with wiki
- **WHEN** the narration service processes a POI with a valid `WikiArticle`
- **THEN** the emitted `MetaEvent` has `is_no_data: false`

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

### Requirement: POIContext carries distance_m
The backend `POIContext` data model SHALL include a `distance_m: float` field (defaults to `0.0`) representing the distance in metres from the user's current position to the POI at the time of narration selection.

#### Scenario: distance_m defaults to zero
- **WHEN** `POIContext` is constructed without `distance_m`
- **THEN** `poi_context.distance_m == 0.0`

#### Scenario: narration API passes distance_m from selected POI
- **WHEN** the narration API endpoint constructs `POIContext` for the selected POI
- **THEN** `poi_context.distance_m` equals `selected.distance_m`

---

### Requirement: PromptBuilder injects distance_hint
`PromptBuilder.build()` SHALL derive a natural-language distance hint from `poi.distance_m` and inject it as `{distance_hint}` into the persona's `narration_template`. The binning rules (for `zh-TW`) are:

| distance_m range | zh-TW hint | en hint |
|---|---|---|
| < 30 | `就在你附近` | `right here` |
| 30 – 150 | `前方不遠處` | `not far ahead` |
| 150 – 500 | `這附近` | `nearby` |
| > 500 | `這一帶` | `in this area` |

#### Scenario: distance < 30m maps to closest hint
- **WHEN** `poi.distance_m == 15.0` and `lang == "zh-TW"`
- **THEN** the user message in the prompt contains `就在你附近`

#### Scenario: distance 30–150m maps to medium-close hint
- **WHEN** `poi.distance_m == 80.0` and `lang == "zh-TW"`
- **THEN** the user message contains `前方不遠處`

#### Scenario: distance 150–500m maps to area hint
- **WHEN** `poi.distance_m == 250.0` and `lang == "zh-TW"`
- **THEN** the user message contains `這附近`

#### Scenario: distance > 500m maps to widest hint
- **WHEN** `poi.distance_m == 800.0` and `lang == "zh-TW"`
- **THEN** the user message contains `這一帶`

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
`NarrationNotifier` SHALL resolve the played POI by matching `MetaEvent.poiId` against the candidates list. If no match is found, it SHALL fall back to `candidates.first`. When `MetaEvent.isNoData == true` and the previous narration also had `isNoData == true` (i.e., `_lastWasNoData == true`), `NarrationNotifier` SHALL immediately cancel the SSE subscription, skip audio playback, and transition to `idle` without recording a narration history entry.

#### Scenario: POI resolved from MetaEvent poi_id
- **WHEN** MetaEvent arrives with `poi_id` matching a candidate in the list
- **THEN** `NarrationState.currentPoi` is set to the matched candidate

#### Scenario: Fallback to first candidate on unmatched poi_id
- **WHEN** MetaEvent `poi_id` does not match any candidate
- **THEN** `NarrationState.currentPoi` is set to `candidates.first`

#### Scenario: First consecutive no-data narration plays normally
- **WHEN** `MetaEvent.isNoData == true` and `_lastWasNoData == false`
- **THEN** narration proceeds normally, `_lastWasNoData` is set to `true`

#### Scenario: Second consecutive no-data narration is suppressed
- **WHEN** `MetaEvent.isNoData == true` and `_lastWasNoData == true`
- **THEN** SSE subscription is cancelled immediately, no audio is played, and `NarrationState.status` transitions to `idle`

#### Scenario: Non-no-data narration resets flag
- **WHEN** `MetaEvent.isNoData == false` arrives
- **THEN** `_lastWasNoData` is set to `false` and narration proceeds normally

---

### Requirement: FIFO audio queue playback
The app SHALL decode each audio chunk and enqueue it for continuous playback using just_audio ConcatenatingAudioSource. Audio chunks are in MP3 format (produced by Edge TTS). `NarrationNotifier` SHALL NOT transition to `idle` status immediately upon receiving `EndEvent`; it SHALL wait until `AudioPlayerService.isPlayingStream` emits `false` after the SSE stream has ended.

#### Scenario: First audio chunk starts playback immediately
- **WHEN** the first `AudioEvent` is received
- **THEN** audio playback begins within ~2 seconds (time to decode + buffer)

#### Scenario: Subsequent chunks play continuously
- **WHEN** additional `AudioEvent`s arrive while playback is running
- **THEN** each decoded MP3 chunk is appended to the queue and plays without gap

#### Scenario: Session ends, temp files cleaned up
- **WHEN** session transitions to `idle`
- **THEN** all temp audio files (`narration_*.mp3`) under `getTemporaryDirectory()` are deleted

#### Scenario: NarrationStatus stays playing after EndEvent until audio stops
- **WHEN** SSE stream emits `EndEvent` but audio is still playing
- **THEN** `NarrationState.status` remains `playing` until `AudioPlayerService.isPlayingStream` emits `false`

#### Scenario: NarrationStatus transitions to idle when audio finishes
- **WHEN** `AudioPlayerService.isPlayingStream` emits `false` after `EndEvent` has been received
- **THEN** `NarrationState.status` transitions to `idle`

#### Scenario: Audio already done when EndEvent arrives
- **WHEN** `EndEvent` arrives and `isPlayingStream` is already emitting `false`
- **THEN** `NarrationState.status` transitions to `idle` immediately

---

### Requirement: Queue-friendly narration stop boundary
`NarrationNotifier` SHALL expose a stop-current operation that cancels the active SSE subscription, resets queued audio playback state, and transitions narration back to `idle` without deciding what the next POI should be. Queue and session owners SHALL use that boundary to advance playback or clear state. The existing user-facing skip action SHALL delegate to the same stop-current behavior.

#### Scenario: Queue stop-current resets active narration to idle
- **WHEN** queue management requests the current narration to stop while audio or SSE streaming is active
- **THEN** `NarrationNotifier` cancels the active playback pipeline and transitions to `idle`

#### Scenario: User skip delegates to stop-current behavior
- **WHEN** the user activates skip while narration is active
- **THEN** the app uses the same stop-current path that queue advancement uses

---

### Requirement: NarrationSheet subtitle and controls
The narration sheet SHALL remain a draggable playback surface with a collapsed mini bar and an expanded subtitle/controls view. When queue mode is active, the collapsed and expanded controls SHALL expose the current POI plus minimal next-item queue state, and the skip control SHALL mean "next tour item" rather than "drop audio only".

#### Scenario: Collapsed mini bar shows next queued POI
- **WHEN** narration is active and the queue has another waiting POI
- **THEN** the mini bar shows the current POI plus the next queued POI name and queued count

#### Scenario: Skip control advances to the next queued POI
- **WHEN** the user taps skip while queue mode has a waiting item
- **THEN** the current narration stops and the next valid queued POI starts through the queue provider

#### Scenario: Existing playback controls remain visible without a queued item
- **WHEN** narration is active but no next queued POI exists
- **THEN** the narration sheet still shows the current POI and normal playback controls without queue metadata

---

### Requirement: Narration error handling
The app SHALL handle backend errors gracefully during narration.

#### Scenario: Gemini 429 rate limit
- **WHEN** SSE stream yields an `ErrorEvent` with `code: "RATE_LIMITED"` and `retry_after_s: N`
- **THEN** NarrationProvider enters error state and MapScreen shows a countdown snackbar

#### Scenario: SSE stream disconnects mid-stream
- **WHEN** the HTTP connection drops while SSE events are still expected
- **THEN** AudioPlayer finishes playing already-enqueued chunks, then stops; a snackbar informs the user

#### Scenario: Backend 5xx or no response
- **WHEN** `POST /narration` returns 5xx or times out
- **THEN** BackendClient retries 3 times (1s/2s/4s backoff); on final failure NarrationProvider enters error state
