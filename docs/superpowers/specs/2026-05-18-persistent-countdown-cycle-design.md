# Persistent Countdown Cycle Design

**Date:** 2026-05-18  
**Status:** Approved

## Problem

The trigger engine gets stuck when `_doCandidatesRequest()` returns early without restarting the countdown. Three cases cause this stuck state:

1. `available.isEmpty` — all nearby POIs already played
2. Dedup guard blocks — user hasn't moved and POI list is nearly identical (jaccard ≥ 0.8)
3. SkipEvent — LLM decided all candidates are trivial → enters displacement-wait mode instead of countdown

Once stuck, the CountdownBadge disappears and no narration ever fires again, even when the user moves to a new area.

## Design

### Principle

The 90-second countdown is the heartbeat of the trigger engine. It must always restart after any non-narration outcome, so the badge is always visible and the system never stalls.

### State Model (`TriggerState`)

Remove all displacement-wait fields. `TriggerState` only tracks countdown:

```dart
class TriggerState {
  final bool isCountingDown;
  final Duration countdownRemaining;
}
```

Removed fields: `isWaitingForDisplacement`, `skipLat`, `skipLon`, `movedMeters`.

### `_startCountdown()` Behavior

**Do NOT reset** `_lastTriggerPosition` or `_lastCandidateIds`. Position tracking must persist across countdown cycles so the dedup guard works correctly on the next fire.

```dart
void _startCountdown() {
  _locationSub?.cancel();
  _locationSub = null;
  _cooldownTimer?.cancel();
  // Position tracking NOT reset — dedup applies across cycles
  final seconds = ref.read(appSettingsProvider).countdownSeconds;
  ...
}
```

### `skipCountdown()` Behavior

User explicitly taps the badge to skip waiting. Force-bypass dedup by resetting tracking:

```dart
void skipCountdown() {
  _cooldownTimer?.cancel();
  _cooldownTimer = null;
  _cooldownUntil = null;
  _lastTriggerPosition = null;   // bypass dedup on manual skip
  _lastCandidateIds = {};
  state = const TriggerState();
  _doCandidatesRequest()...;
}
```

### `_doCandidatesRequest()` Decision Tree

```
if (_latestPois.isEmpty)
  → return  (no restart — POIs not loaded yet, first load triggers separately)

if (narration playing/loading)
  → return  (no restart — narration completion will call _startCountdown())

if (app not resumed)
  → return  (no restart — avoids background infinite loop)

available = _latestPois − sessionPlayedIds − cooldownIds

if (available.isEmpty)
  → _startCountdown()   ← NEW
  → return

// Dedup guard
if (_lastTriggerPosition != null && moved < 30m && jaccard ≥ 0.8)
  → _startCountdown()   ← NEW
  → return

// All checks passed
_lastTriggerPosition = _currentPosition
_lastCandidateIds = available ids
narrate()
```

### SkipEvent Handling

Replace `_handleSkip()` (displacement-wait) with `_startCountdown()`. Position was already saved in `_doCandidatesRequest()` before calling `narrate()`, so the next countdown cycle correctly checks for movement.

```dart
// In narrationProvider listener:
if (next.lastEventWasSkip && !(prev?.lastEventWasSkip ?? false)) {
  _startCountdown();  // replaces _handleSkip()
}
```

Remove `_handleSkip()` and `_startDisplacementWatch()` methods entirely.

### Complete Cycle Behavior

| Outcome | Next action |
|---|---|
| Narration completes normally | `_startCountdown()` (position NOT reset) |
| `available.isEmpty` | `_startCountdown()` (position NOT reset) |
| Dedup guard blocks | `_startCountdown()` (position NOT reset) |
| LLM SKIP (SkipEvent) | `_startCountdown()` (position saved from narrate call) |
| User taps badge | `skipCountdown()` → resets position → immediate trigger |
| Error during narration | `_startCountdown()` (existing behavior, unchanged) |

### UI Changes (`countdown_badge.dart`)

Remove `_DisplacementBadge` widget and the `isWaitingForDisplacement` branch. `CountdownBadge` has one state: show circle countdown when `isCountingDown`, hide otherwise.

## Testing

### Modified Tests

| Test | Change |
|---|---|
| `SkipEvent sets isWaitingForDisplacement` | Rename + assert `isCountingDown = true` instead |

### New Tests

1. `available.isEmpty` → countdown fires → `isCountingDown = true` restarts
2. Dedup guard blocks → `isCountingDown = true` restarts
