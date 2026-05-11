## ADDED Requirements

### Requirement: SSE stream parsing
The app SHALL parse `POST /narration` SSE responses into typed events: `meta`, `text`, `audio`, `end`, `error`.

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

#### Scenario: Partial chunk boundary
- **WHEN** a TCP packet splits an SSE block in the middle
- **THEN** SseParser buffers partial data and only yields the event after the complete `\n\n` delimiter is received

### Requirement: FIFO audio queue playback
The app SHALL decode each audio chunk and enqueue it for continuous playback using just_audio ConcatenatingAudioSource.

#### Scenario: First audio chunk starts playback immediately
- **WHEN** the first `AudioEvent` is received
- **THEN** audio playback begins within ~2 seconds (time to decode + buffer)

#### Scenario: Subsequent chunks play continuously
- **WHEN** additional `AudioEvent`s arrive while playback is running
- **THEN** each decoded chunk is appended to the queue and plays without gap

#### Scenario: Session ends, temp files cleaned up
- **WHEN** session transitions to `idle`
- **THEN** all temp audio files under `getTemporaryDirectory()` are deleted

### Requirement: NarrationSheet subtitle and controls
The NarrationSheet SHALL be a DraggableScrollableSheet showing a collapsed MiniBar and an expanded subtitle/controls view.

#### Scenario: Collapsed mini bar
- **WHEN** NarrationSheet is in collapsed state
- **THEN** shows POI name, distance, ▶/⏸ button, and ⏭ skip button

#### Scenario: Expanded subtitle view
- **WHEN** NarrationSheet is dragged up to expanded state
- **THEN** shows POI name, confidence badge, scrolling subtitle text, progress bar, and ⏸/⏭/🔁 controls

#### Scenario: Subtitle accumulates text chunks
- **WHEN** `TextEvent`s arrive during narration
- **THEN** each chunk is appended to the subtitle display in real time

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
