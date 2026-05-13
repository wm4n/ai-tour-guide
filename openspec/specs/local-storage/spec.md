# Capability: Local Storage

## Purpose

Provides persistent local storage using SQLite (drift) for journey session records and narration history, including a 24-hour cooldown query used by TriggerEngine.

---

## Requirements

### Requirement: Session records in SQLite
The app SHALL store each journey session in a `sessions` table with start/end timestamps, persona, and language.

#### Scenario: Session started
- **WHEN** SessionProvider.start() succeeds
- **THEN** a new row is inserted into `sessions` with `started_at` = current timestamp, `persona = "history_uncle"`, `lang = "zh-TW"`, `ended_at = NULL`

#### Scenario: Session ended
- **WHEN** SessionProvider.stop() is called
- **THEN** the current session row is updated with `ended_at` = current timestamp

---

### Requirement: Narration history records
The app SHALL store each narration play event in a `narration_history` table.

#### Scenario: Narration completed
- **WHEN** SSE stream emits `EndEvent` for a POI
- **THEN** a row is inserted into `narration_history` with `completed = 1`, `played_at` = current timestamp, and all POI fields

#### Scenario: Narration skipped
- **WHEN** user taps ⏭ skip before narration completes
- **THEN** a row is inserted into `narration_history` with `completed = 0`

---

### Requirement: 24-hour cooldown query
The app SHALL provide a fast cooldown check: has this POI been played within the last 24 hours?

#### Scenario: POI played within cooldown window
- **WHEN** `isCooldown(poi.id, Duration(hours: 24))` is called and a history row exists with `played_at` within the last 24 hours
- **THEN** returns `true`

#### Scenario: POI not played recently
- **WHEN** no history row exists for the POI, or the latest row's `played_at` is older than 24 hours
- **THEN** returns `false`

#### Scenario: In-memory DB for testing
- **WHEN** `LocalDb.forTesting(NativeDatabase.memory())` is used in tests
- **THEN** the DB runs fully in memory with no file I/O, allowing isolated unit tests
