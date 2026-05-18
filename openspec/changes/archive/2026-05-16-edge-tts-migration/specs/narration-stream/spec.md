## MODIFIED Requirements

### Requirement: FIFO audio queue playback
The app SHALL decode each audio chunk and enqueue it for continuous playback using just_audio ConcatenatingAudioSource. Audio chunks are in MP3 format (produced by Edge TTS).

#### Scenario: First audio chunk starts playback immediately
- **WHEN** the first `AudioEvent` is received
- **THEN** audio playback begins within ~2 seconds (time to decode + buffer)

#### Scenario: Subsequent chunks play continuously
- **WHEN** additional `AudioEvent`s arrive while playback is running
- **THEN** each decoded MP3 chunk is appended to the queue and plays without gap

#### Scenario: Session ends, temp files cleaned up
- **WHEN** session transitions to `idle`
- **THEN** all temp audio files (`narration_*.mp3`) under `getTemporaryDirectory()` are deleted
