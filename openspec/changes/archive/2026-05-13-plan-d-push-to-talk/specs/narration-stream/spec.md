## MODIFIED Requirements

### Requirement: FIFO audio queue playback
The app SHALL decode each audio chunk and enqueue it for continuous playback using just_audio ConcatenatingAudioSource. The AudioPlayerService interface SHALL additionally expose `duck()` and `unduck()` methods to support volume control for Q&A ducking.

#### Scenario: First audio chunk starts playback immediately
- **WHEN** the first `AudioEvent` is received
- **THEN** audio playback begins within ~2 seconds (time to decode + buffer)

#### Scenario: Subsequent chunks play continuously
- **WHEN** additional `AudioEvent`s arrive while playback is running
- **THEN** each decoded chunk is appended to the queue and plays without gap

#### Scenario: Session ends, temp files cleaned up
- **WHEN** session transitions to `idle`
- **THEN** all temp audio files under `getTemporaryDirectory()` are deleted

#### Scenario: Duck reduces volume to 50%
- **WHEN** `duck()` is called on AudioPlayerService
- **THEN** playback volume is reduced to 0.5 (50%) immediately without pausing

#### Scenario: Unduck restores volume to 100%
- **WHEN** `unduck()` is called on AudioPlayerService
- **THEN** playback volume is restored to 1.0 (100%) immediately

#### Scenario: FakeAudioPlayerService tracks duck state
- **WHEN** `duck()` is called on FakeAudioPlayerService
- **THEN** `isDucked` property is set to true, enabling test assertions

#### Scenario: FakeAudioPlayerService tracks unduck state
- **WHEN** `unduck()` is called on FakeAudioPlayerService after duck()
- **THEN** `isDucked` property is set to false
