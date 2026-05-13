## ADDED Requirements

### Requirement: Push-to-talk recording
The app SHALL allow users to initiate a voice question by long-pressing the PushToTalkButton on MapScreen, recording until they release the button.

#### Scenario: Long press starts recording
- **WHEN** user long-presses the PushToTalkButton while session is active
- **THEN** MicRecorderService begins recording WAV audio and QaNotifier transitions to `recording` state

#### Scenario: Button shows recording state
- **WHEN** QaNotifier status is `recording`
- **THEN** PushToTalkButton displays a red pulsing animation with microphone icon

#### Scenario: Button hidden when session inactive
- **WHEN** session status is not `active`
- **THEN** PushToTalkButton is not visible (SizedBox.shrink)

#### Scenario: Short press cancelled silently
- **WHEN** user releases the button within 500ms of pressing
- **THEN** recording is cancelled silently without sending a request and QaNotifier returns to `idle`

---

### Requirement: Q&A audio submission and response streaming
The app SHALL send recorded audio to the backend and stream the Q&A response as SSE events.

#### Scenario: Audio submitted after release
- **WHEN** user releases PushToTalkButton after recording >= 500ms
- **THEN** MicRecorderService stops recording, WAV bytes are POSTed to `/qa` as multipart/form-data with persona, lang, currentPoiId, and narrationSoFar context

#### Scenario: Processing state shown
- **WHEN** audio is submitted and awaiting transcript
- **THEN** PushToTalkButton displays CircularProgressIndicator and QaNotifier status is `processing`

#### Scenario: Transcript received and displayed
- **WHEN** backend emits a `transcript` SSE event
- **THEN** QaNotifier transitions to `answering` and NarrationSheet shows "你說：<transcript text>" above existing subtitle

#### Scenario: Response text accumulated
- **WHEN** backend emits `text` SSE events
- **THEN** QaNotifier appends each chunk to responseText and NarrationSheet shows accumulated response

#### Scenario: Q&A audio played via independent player
- **WHEN** backend emits `audio` SSE events with base64 WAV chunks
- **THEN** each chunk is decoded and enqueued to qaAudioPlayerProvider (separate from narration AudioPlayer)

#### Scenario: Q&A completes
- **WHEN** backend emits `end` SSE event
- **THEN** QaNotifier transitions back to `idle` and narration audio volume is restored to 100%

---

### Requirement: Narration ducking during Q&A
The app SHALL reduce narration audio volume to 50% while Q&A is active and restore it when Q&A ends.

#### Scenario: Narration ducked on recording start
- **WHEN** QaNotifier.startRecording() is called
- **THEN** narrationAudioPlayerProvider.duck() is called and narration volume is set to 50%

#### Scenario: Narration unducked on Q&A complete
- **WHEN** backend emits `end` or `error` SSE event
- **THEN** narrationAudioPlayerProvider.unduck() is called and narration volume is restored to 100%

#### Scenario: Narration unducked on cancel
- **WHEN** QaNotifier.cancelRecording() is called
- **THEN** narrationAudioPlayerProvider.unduck() is called immediately

---

### Requirement: Q&A error handling
The app SHALL handle Q&A errors gracefully without disrupting the narration stream.

#### Scenario: STT transcription failure
- **WHEN** backend emits an `error` SSE event with STT-related code
- **THEN** QaNotifier transitions to `error` state, narration audio is unducked, and PushToTalkButton shows orange warning icon

#### Scenario: Q&A interrupted by new long press
- **WHEN** user long-presses PushToTalkButton while QaNotifier status is `answering`
- **THEN** current Q&A stream subscription is cancelled, qaAudio is skipped, narration is unducked, then new recording starts

#### Scenario: Session ends during Q&A
- **WHEN** sessionProvider.isActive becomes false while Q&A is in progress
- **THEN** MapScreen calls qaProvider.notifier.cancelRecording(), narration is unducked, and QaNotifier returns to idle

---

### Requirement: Backend /qa SSE endpoint
The backend SHALL expose a `POST /qa` endpoint that accepts audio and context, and streams STT → LLM → TTS results as SSE events.

#### Scenario: Valid request returns SSE stream
- **WHEN** a valid multipart POST is sent to `/qa` with `audio` WAV bytes and `context` JSON containing persona, lang, currentPoiId, narrationSoFar
- **THEN** response is `text/event-stream` with events in order: `transcript` → one or more `text`+`audio` pairs → `end`

#### Scenario: Unknown persona returns 400
- **WHEN** context JSON contains a persona ID not in the persona registry
- **THEN** endpoint returns HTTP 400 with an error message listing valid personas

#### Scenario: Missing audio field returns 422
- **WHEN** POST request does not include the `audio` file field
- **THEN** endpoint returns HTTP 422

#### Scenario: Transcript event is first
- **WHEN** QAService processes the request
- **THEN** the first SSE event MUST be `transcript` with the transcribed question text

#### Scenario: End event is last
- **WHEN** QAService completes the STT→LLM→TTS pipeline
- **THEN** the final SSE event MUST be `end`

---

### Requirement: QAService STT→LLM→TTS pipeline
The backend SHALL implement QAService that orchestrates the full Q&A pipeline using provider abstractions.

#### Scenario: SttProvider transcribes audio
- **WHEN** QAService.answer() is called with audio bytes and lang
- **THEN** SttProvider.transcribe() is called and the result is used as user_question in the LLM prompt

#### Scenario: PromptBuilder.build_qa with POI context
- **WHEN** current_poi_name is provided
- **THEN** QAService uses PromptBuilder.build_qa() with poi_name, narration_summary, and user_question filled in from persona's qa_template

#### Scenario: PromptBuilder.build_qa without POI context
- **WHEN** current_poi_name is None
- **THEN** QAService uses a general Q&A prompt format asking persona to respond naturally to the user's question

#### Scenario: LLM response split into sentences and TTS synthesized
- **WHEN** LLM streams text chunks
- **THEN** StreamingSentenceBuffer splits into sentences, each sentence is synthesized via TtsProvider, yielding TextEvent+AudioEvent pairs per sentence
