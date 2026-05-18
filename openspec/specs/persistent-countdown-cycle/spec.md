# Capability: Persistent Countdown Cycle

## Purpose

Ensures the trigger engine maintains a continuous countdown heartbeat that handles non-narration outcomes (no candidates, dedup guard blocks, skip events) by restarting the countdown timer, preventing the system from reaching a stuck state.

---

## Requirements

### Requirement: Persistent countdown cycle as system heartbeat
The trigger engine SHALL treat the countdown timer as a heartbeat mechanism. Any non-narration outcome from `_doCandidatesRequest()` — including `available.isEmpty`, dedup guard block, or SkipEvent from LLM — SHALL restart the countdown. The system SHALL never reach a state where no countdown is active and no narration is playing, unless narration is actively loading or playing.

#### Scenario: available.isEmpty restarts countdown
- **WHEN** `_doCandidatesRequest()` finds all POIs excluded (session-played or cooldown)
- **THEN** `_startCountdown()` is called and `TriggerState.isCountingDown` becomes true

#### Scenario: Dedup guard block restarts countdown
- **WHEN** `_doCandidatesRequest()` is blocked by the dedup guard (moved < 30m and Jaccard ≥ 0.8)
- **THEN** `_startCountdown()` is called and `TriggerState.isCountingDown` becomes true

#### Scenario: SkipEvent restarts countdown
- **WHEN** `NarrationState.lastEventWasSkip` becomes true (LLM returned SkipEvent)
- **THEN** `_startCountdown()` is called and `TriggerState.isCountingDown` becomes true

#### Scenario: Heartbeat continues until narration triggers
- **WHEN** countdown expires and dedup guard blocks the request again
- **THEN** countdown restarts, forming a heartbeat loop that continues until user moves or POIs change
