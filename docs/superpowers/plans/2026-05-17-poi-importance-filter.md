# POI 重要性過濾 + 位移等待 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the LLM decides all nearby POIs are trivial, return a SKIP signal, and wait for the user to move 1.5km (configurable) before re-triggering narration.

**Architecture:** `POISelectorService.select()` returns `str | None` — `None` means skip. The backend streams a `skip` SSE event; Flutter's `NarrationNotifier` sets `lastEventWasSkip = true`; `TriggerNotifier` detects this, subscribes to location, and re-triggers once displacement threshold is reached. A new Settings Screen lets users adjust the threshold and countdown duration.

**Tech Stack:** Python (FastAPI, SSE), Dart/Flutter (Riverpod StateNotifier/Notifier, shared_preferences), geolocator haversine utility already exists at `flutter_app/lib/shared/location/haversine.dart`.

---

## File Map

| Action | File |
|--------|------|
| Modify | `backend/src/tour_guide/services/poi_selector.py` |
| Modify | `backend/src/tour_guide/api/narration.py` |
| Modify | `backend/src/tour_guide/log_events.py` |
| Modify | `backend/tests/unit/test_poi_selector.py` |
| Modify | `flutter_app/pubspec.yaml` |
| Modify | `flutter_app/lib/shared/backend/models/narration_event.dart` |
| Modify | `flutter_app/lib/shared/backend/backend_client.dart` |
| Create | `flutter_app/lib/shared/settings/app_settings.dart` |
| Create | `flutter_app/lib/shared/settings/settings_provider.dart` |
| Modify | `flutter_app/lib/features/narration/providers/narration_provider.dart` |
| Modify | `flutter_app/lib/features/narration/providers/trigger_provider.dart` |
| Modify | `flutter_app/lib/features/narration/widgets/countdown_badge.dart` |
| Create | `flutter_app/lib/features/settings/settings_screen.dart` |
| Modify | `flutter_app/lib/features/map/screens/map_screen.dart` |
| Modify | `flutter_app/test/unit/trigger_provider_test.dart` |
| Create | `flutter_app/test/unit/settings_provider_test.dart` |

---

## Task 1: Backend — poi_selector SKIP support

**Files:**
- Modify: `backend/src/tour_guide/services/poi_selector.py`
- Modify: `backend/src/tour_guide/log_events.py`
- Modify: `backend/tests/unit/test_poi_selector.py`

- [ ] **Step 1.1: Add `POI_SELECTION_SKIP` log event**

In `backend/src/tour_guide/log_events.py`, add after `POI_SELECTION`:

```python
    POI_SELECTION_SKIP = "POI_SELECTION_SKIP"
```

- [ ] **Step 1.2: Write failing tests for SKIP behaviour**

Append to `backend/tests/unit/test_poi_selector.py`:

```python
@pytest.mark.asyncio
async def test_selector_returns_none_when_llm_says_skip(fake_persona):
    candidates = [
        POICandidate(poi_id="node/1", poi_name="地圖map", distance_m=30, wiki_extract=None),
        POICandidate(poi_id="node/2", poi_name="導覽圖", distance_m=50, wiki_extract=None),
    ]
    llm = make_fake_llm("SKIP")
    service = POISelectorService(llm=llm)
    selected = await service.select(candidates=candidates, persona=fake_persona, lang="zh-TW")
    assert selected is None


@pytest.mark.asyncio
async def test_selector_falls_back_to_first_on_invalid_not_skip(fake_persona):
    candidates = [
        POICandidate(poi_id="node/A", poi_name="故宮", distance_m=50, wiki_extract="info"),
    ]
    llm = make_fake_llm("bad_id_that_is_not_skip")
    service = POISelectorService(llm=llm)
    selected = await service.select(candidates=candidates, persona=fake_persona, lang="zh-TW")
    assert selected == "node/A"
```

- [ ] **Step 1.3: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/unit/test_poi_selector.py -v -k "skip"
```
Expected: `FAILED` with `AssertionError` (select() currently returns string, not None).

- [ ] **Step 1.4: Update `poi_selector.py` to support SKIP**

Replace the entire `select()` method and return type in `backend/src/tour_guide/services/poi_selector.py`:

```python
    async def select(
        self,
        candidates,   # list[POICandidate]
        persona: PersonaConfig,
        lang: str,
        previous=None,  # PreviousSelection | None
    ) -> str | None:
        """Return poi_id of best candidate, or None if all candidates are trivial (SKIP)."""
        if not candidates:
            raise ValueError("candidates list is empty")

        candidate_lines = "\n".join(
            f"- [{c.poi_id}] {c.poi_name} ({c.distance_m:.0f}m)"
            f"{' [has Wikipedia]' if c.wiki_extract else ' [no Wikipedia]'}"
            for c in candidates
        )

        previous_section = ""
        if previous is not None:
            preview = previous.script[:400] + ("..." if len(previous.script) > 400 else "")
            previous_section = (
                f"\n\nPrevious narration:\n"
                f"POI: {previous.poi_name}\n"
                f"Script preview: {preview}"
            )

        user_content = (
            f"Select the single best POI to narrate for a {lang} tour guide "
            f"with persona '{persona.id}'.\n\n"
            f"Candidates:\n{candidate_lines}"
            f"{previous_section}\n\n"
            f"Rules:\n"
            f"- Prefer POIs with Wikipedia data\n"
            f"- Prefer closer POIs over farther ones when quality is similar\n"
            f"- Avoid choosing the same theme as the previous narration\n"
            f"- If ALL candidates are trivial (maps/signs/boards/bus stops with no Wikipedia), "
            f"reply with SKIP\n"
            f"- Trivial examples: names containing 地圖/map/導覽圖/公車/巴士/bus/signboard/"
            f"information board, AND no Wikipedia data\n"
            f"- Worth narrating: has Wikipedia data, OR is a named attraction/monument/"
            f"building/park/temple\n"
            f"- Reply with ONLY the poi_id or ONLY the word SKIP — nothing else"
        )

        messages = [
            Message(role="system", content="You are a tour guide POI selector. Output only the poi_id or SKIP."),
            Message(role="user", content=user_content),
        ]
        opts = LlmOpts(temperature=0.1, max_tokens=64)

        result = ""
        async for chunk in self._llm.chat_stream(messages, opts):
            result += chunk
        selected_id = result.strip()

        if selected_id == "SKIP":
            log_event(
                logger,
                LogEvents.POI_SELECTION_SKIP,
                candidate_count=len(candidates),
                has_previous=previous is not None,
            )
            return None

        valid_ids = {c.poi_id for c in candidates}
        if selected_id not in valid_ids:
            logger.warning(
                "POI selector returned invalid id '%s', falling back to first candidate", selected_id
            )
            selected_id = candidates[0].poi_id

        log_event(
            logger,
            LogEvents.POI_SELECTION,
            selected_id=selected_id,
            candidate_count=len(candidates),
            has_previous=previous is not None,
        )
        return selected_id
```

- [ ] **Step 1.5: Run all poi_selector tests**

```bash
cd backend && python -m pytest tests/unit/test_poi_selector.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 1.6: Commit**

```bash
git add backend/src/tour_guide/services/poi_selector.py \
        backend/src/tour_guide/log_events.py \
        backend/tests/unit/test_poi_selector.py
git commit -m "feat(backend): poi_selector returns None (SKIP) for trivial candidates"
```

---

## Task 2: Backend — narration endpoint handles SKIP

**Files:**
- Modify: `backend/src/tour_guide/api/narration.py`

- [ ] **Step 2.1: Write failing test for skip SSE response**

Create `backend/tests/unit/test_narration_skip.py`:

```python
"""Tests for SKIP path in narration endpoint."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from tour_guide.api import narration as narration_module
from tour_guide.api.narration import NarrationRequest, POICandidate
from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle


def _make_persona():
    return PersonaConfig(
        id="history_uncle",
        display_name={"zh-TW": "歷史大叔"},
        voice={"zh-TW": "zh-TW-YunJheNeural"},
        voice_style=VoiceStyle(speaking_rate=1.0, emotion="neutral"),
        style_profile=StyleProfile(embellishment=0.0, preferred_topics=[]),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是歷史大叔"},
        narration_template={"zh-TW": "narrate {poi_name}"},
        qa_template={"zh-TW": "answer"},
        no_data_context={"zh-TW": "不熟"},
    )


def _make_app(selector_returns=None):
    app = FastAPI()
    app.include_router(narration_module.router)

    fake_selector = MagicMock()
    fake_selector.select = AsyncMock(return_value=selector_returns)

    fake_narration = MagicMock()

    app.dependency_overrides[narration_module.get_poi_selector_service] = lambda: fake_selector
    app.dependency_overrides[narration_module.get_narration_service] = lambda: fake_narration
    app.dependency_overrides[narration_module.get_persona_registry] = lambda: {
        "history_uncle": _make_persona()
    }
    return app


def test_skip_returns_skip_sse_event():
    app = _make_app(selector_returns=None)
    client = TestClient(app)
    payload = {
        "candidates": [
            {"poi_id": "node/1", "poi_name": "地圖", "distance_m": 30}
        ],
        "persona": "history_uncle",
        "lang": "zh-TW",
    }
    response = client.post("/narration", json=payload, headers={"Accept": "text/event-stream"})
    assert response.status_code == 200
    body = response.text
    assert "event: skip" in body
    assert "min_displacement_m" in body
```

- [ ] **Step 2.2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_narration_skip.py -v
```
Expected: FAIL — endpoint currently crashes when `select()` returns `None` (tries to find candidate by None id).

- [ ] **Step 2.3: Update narration.py to handle SKIP**

In `backend/src/tour_guide/api/narration.py`, replace the section after `poi_selector.select(...)` call:

Find and replace the block starting at `# Step 2: Find selected candidate...` with:

```python
    # Step 2: If selector returned None, all candidates are trivial — stream skip event
    if selected_id is None:
        async def skip_stream():
            yield encode_event("skip", {"min_displacement_m": 1500.0})

        return StreamingResponse(
            skip_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Step 3: Find selected candidate and build POIContext
    selected = next((c for c in request.candidates if c.poi_id == selected_id), request.candidates[0])
```

(The rest of the endpoint after `selected = ...` stays exactly the same. Also rename existing `# Step 2:` comment to `# Step 3:` and `# Step 3` doesn't exist — just add the new block before the existing `selected = next(...)` line.)

- [ ] **Step 2.4: Run skip test**

```bash
cd backend && python -m pytest tests/unit/test_narration_skip.py -v
```
Expected: PASS.

- [ ] **Step 2.5: Run full backend test suite**

```bash
cd backend && python -m pytest tests/unit/ -v --ignore=tests/unit/test_config.py
```
Expected: all tests PASS.

- [ ] **Step 2.6: Commit**

```bash
git add backend/src/tour_guide/api/narration.py \
        backend/tests/unit/test_narration_skip.py
git commit -m "feat(backend): stream skip SSE event when poi_selector returns None"
```

---

## Task 3: Flutter — SkipEvent model + SSE parsing

**Files:**
- Modify: `flutter_app/lib/shared/backend/models/narration_event.dart`
- Modify: `flutter_app/lib/shared/backend/backend_client.dart`

- [ ] **Step 3.1: Add `SkipEvent` to narration_event.dart**

In `flutter_app/lib/shared/backend/models/narration_event.dart`, append before the last `}` (after `ErrorEvent`):

```dart
class SkipEvent extends NarrationEvent {
  final double minDisplacementM;
  const SkipEvent({this.minDisplacementM = 1500.0});

  factory SkipEvent.fromJson(Map<String, dynamic> json) => SkipEvent(
        minDisplacementM: (json['min_displacement_m'] as num?)?.toDouble() ?? 1500.0,
      );
}
```

- [ ] **Step 3.2: Update `_toNarrationEvent` in backend_client.dart**

In `flutter_app/lib/shared/backend/backend_client.dart`, find `_toNarrationEvent` and replace:

```dart
  NarrationEvent? _toNarrationEvent(SseEvent sse) => switch (sse.type) {
        'meta' => MetaEvent.fromJson(sse.data),
        'text' => TextEvent.fromJson(sse.data),
        'audio' => AudioEvent.fromJson(sse.data),
        'end' => const EndEvent(),
        'error' => ErrorEvent.fromJson(sse.data),
        'skip' => SkipEvent.fromJson(sse.data),
        _ => null,
      };
```

(Change `_ => ErrorEvent(code: 'unknown', ...)` to `_ => null` so unknown events are silently dropped.)

- [ ] **Step 3.3: Verify it compiles**

```bash
cd flutter_app && flutter analyze lib/shared/backend/
```
Expected: no errors.

- [ ] **Step 3.4: Commit**

```bash
git add flutter_app/lib/shared/backend/models/narration_event.dart \
        flutter_app/lib/shared/backend/backend_client.dart
git commit -m "feat(flutter): add SkipEvent to narration SSE model and parser"
```

---

## Task 4: Flutter — AppSettings + shared_preferences

**Files:**
- Modify: `flutter_app/pubspec.yaml`
- Create: `flutter_app/lib/shared/settings/app_settings.dart`
- Create: `flutter_app/lib/shared/settings/settings_provider.dart`
- Create: `flutter_app/test/unit/settings_provider_test.dart`

- [ ] **Step 4.1: Add shared_preferences to pubspec.yaml**

In `flutter_app/pubspec.yaml`, under `dependencies:`, add:

```yaml
  shared_preferences: ^2.3.2
```

Then run:
```bash
cd flutter_app && flutter pub get
```
Expected: resolves without conflicts.

- [ ] **Step 4.2: Create app_settings.dart**

Create `flutter_app/lib/shared/settings/app_settings.dart`:

```dart
class AppSettings {
  final double skipDisplacementM;
  final int countdownSeconds;

  const AppSettings({
    this.skipDisplacementM = 1500.0,
    this.countdownSeconds = 90,
  });

  AppSettings copyWith({double? skipDisplacementM, int? countdownSeconds}) =>
      AppSettings(
        skipDisplacementM: skipDisplacementM ?? this.skipDisplacementM,
        countdownSeconds: countdownSeconds ?? this.countdownSeconds,
      );
}
```

- [ ] **Step 4.3: Write failing tests for settings provider**

Create `flutter_app/test/unit/settings_provider_test.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('AppSettings defaults are correct', () {
    const settings = AppSettings();
    expect(settings.skipDisplacementM, 1500.0);
    expect(settings.countdownSeconds, 90);
  });

  test('setSkipDisplacement updates state and persists', () async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container.read(appSettingsProvider.notifier).setSkipDisplacement(2000.0);

    expect(container.read(appSettingsProvider).skipDisplacementM, 2000.0);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getDouble('skip_displacement_m'), 2000.0);
  });

  test('setCountdownSeconds updates state and persists', () async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container.read(appSettingsProvider.notifier).setCountdownSeconds(120);

    expect(container.read(appSettingsProvider).countdownSeconds, 120);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getInt('countdown_seconds'), 120);
  });

  test('loads persisted values on init', () async {
    SharedPreferences.setMockInitialValues({
      'skip_displacement_m': 3000.0,
      'countdown_seconds': 60,
    });
    final container = ProviderContainer();
    addTearDown(container.dispose);

    container.listen(appSettingsProvider, (_, __) {});
    await Future<void>.delayed(const Duration(milliseconds: 50));

    final settings = container.read(appSettingsProvider);
    expect(settings.skipDisplacementM, 3000.0);
    expect(settings.countdownSeconds, 60);
  });
}
```

- [ ] **Step 4.4: Run tests to verify they fail**

```bash
cd flutter_app && flutter test test/unit/settings_provider_test.dart
```
Expected: compilation error — `settings_provider.dart` does not exist yet.

- [ ] **Step 4.5: Create settings_provider.dart**

Create `flutter_app/lib/shared/settings/settings_provider.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';

class AppSettingsNotifier extends Notifier<AppSettings> {
  static const _keyDisplacement = 'skip_displacement_m';
  static const _keyCountdown = 'countdown_seconds';

  @override
  AppSettings build() {
    _load();
    return const AppSettings();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = AppSettings(
      skipDisplacementM: prefs.getDouble(_keyDisplacement) ?? 1500.0,
      countdownSeconds: prefs.getInt(_keyCountdown) ?? 90,
    );
  }

  Future<void> setSkipDisplacement(double meters) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_keyDisplacement, meters);
    state = state.copyWith(skipDisplacementM: meters);
  }

  Future<void> setCountdownSeconds(int seconds) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyCountdown, seconds);
    state = state.copyWith(countdownSeconds: seconds);
  }
}

final appSettingsProvider = NotifierProvider<AppSettingsNotifier, AppSettings>(
  AppSettingsNotifier.new,
);
```

- [ ] **Step 4.6: Run settings tests**

```bash
cd flutter_app && flutter test test/unit/settings_provider_test.dart
```
Expected: 4 tests PASS.

- [ ] **Step 4.7: Commit**

```bash
git add flutter_app/pubspec.yaml \
        flutter_app/pubspec.lock \
        flutter_app/lib/shared/settings/app_settings.dart \
        flutter_app/lib/shared/settings/settings_provider.dart \
        flutter_app/test/unit/settings_provider_test.dart
git commit -m "feat(flutter): add AppSettings with SharedPreferences persistence"
```

---

## Task 5: Flutter — NarrationState skip flag

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/narration_provider.dart`

- [ ] **Step 5.1: Add `lastEventWasSkip` to NarrationState**

In `narration_provider.dart`, update `NarrationState` class:

```dart
class NarrationState {
  final NarrationStatus status;
  final POI? currentPoi;
  final String subtitle;
  final String scriptBuffer;
  final double progress;
  final String? confidence;
  final String? errorMessage;
  final bool lastEventWasSkip;      // NEW

  const NarrationState({
    required this.status,
    this.currentPoi,
    this.subtitle = '',
    this.scriptBuffer = '',
    this.progress = 0,
    this.confidence,
    this.errorMessage,
    this.lastEventWasSkip = false,  // NEW
  });

  NarrationState copyWith({
    NarrationStatus? status,
    POI? currentPoi,
    String? subtitle,
    String? scriptBuffer,
    double? progress,
    String? confidence,
    String? errorMessage,
    bool? lastEventWasSkip,         // NEW
  }) =>
      NarrationState(
        status: status ?? this.status,
        currentPoi: currentPoi ?? this.currentPoi,
        subtitle: subtitle ?? this.subtitle,
        scriptBuffer: scriptBuffer ?? this.scriptBuffer,
        progress: progress ?? this.progress,
        confidence: confidence ?? this.confidence,
        errorMessage: errorMessage ?? this.errorMessage,
        lastEventWasSkip: lastEventWasSkip ?? this.lastEventWasSkip,  // NEW
      );
}
```

- [ ] **Step 5.2: Handle SkipEvent in `_handle()`**

In `NarrationNotifier._handle()`, add `SkipEvent` case to the switch. The current switch ends with `case ErrorEvent(...):`. Add after it:

```dart
      case SkipEvent():
        AppLogger.info(LogEvents.narrationSkip, {'reason': 'poi_trivial'});
        state = state.copyWith(
          status: NarrationStatus.idle,
          lastEventWasSkip: true,
        );
```

- [ ] **Step 5.3: Verify it compiles**

```bash
cd flutter_app && flutter analyze lib/features/narration/providers/narration_provider.dart
```
Expected: no errors. (Dart sealed class exhaustive switch now includes SkipEvent.)

- [ ] **Step 5.4: Run existing narration-related tests**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart
```
Expected: existing 3 tests still PASS.

- [ ] **Step 5.5: Commit**

```bash
git add flutter_app/lib/features/narration/providers/narration_provider.dart
git commit -m "feat(flutter): NarrationState.lastEventWasSkip flag set on SkipEvent"
```

---

## Task 6: Flutter — TriggerProvider displacement watch

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **Step 6.1: Write failing tests for displacement behaviour**

In `flutter_app/test/unit/trigger_provider_test.dart`, add at the end of `main()`:

```dart
  test('SkipEvent sets isWaitingForDisplacement and clears countdown', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(
          FakeBackendClient(
            nearbyPois: const [_poi],
            scriptedEvents: const [SkipEvent()],
          ),
        ),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
        sessionLangProvider.overrideWithValue('zh-TW'),
        fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
        appSettingsProvider.overrideWith(
          () => _FakeSettingsNotifier(
            const AppSettings(skipDisplacementM: 500, countdownSeconds: 90),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});

    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));

    final state = container.read(triggerProvider);
    expect(state.isWaitingForDisplacement, isTrue);
    expect(state.isCountingDown, isFalse);
  });

  test('displacement exceeding threshold re-triggers narration', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    // Second call returns EndEvent so we can detect re-trigger
    int callCount = 0;
    final fakeClient = _CountingBackendClient(
      nearbyPois: const [_poi],
      firstEvents: const [SkipEvent()],
      subsequentEvents: const [EndEvent()],
    );

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(fakeClient),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
        sessionLangProvider.overrideWithValue('zh-TW'),
        fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
        appSettingsProvider.overrideWith(
          () => _FakeSettingsNotifier(
            const AppSettings(skipDisplacementM: 100, countdownSeconds: 90),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});

    // Trigger first narration (will get SkipEvent)
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));

    expect(container.read(triggerProvider).isWaitingForDisplacement, isTrue);

    // Move > 100m
    fakeLocation.emit(fakePosition(25.1033, 121.5492)); // ~130m
    await Future<void>.delayed(const Duration(milliseconds: 200));

    expect(container.read(triggerProvider).isWaitingForDisplacement, isFalse);
    expect(fakeClient.callCount, greaterThan(1));
  });
```

Also add these helper classes before `main()`:

```dart
class _FakeSettingsNotifier extends Notifier<AppSettings> {
  final AppSettings _initial;
  _FakeSettingsNotifier(this._initial);
  @override
  AppSettings build() => _initial;
}

class _CountingBackendClient implements BackendClient {
  final List<POI> nearbyPois;
  final List<NarrationEvent> firstEvents;
  final List<NarrationEvent> subsequentEvents;
  int callCount = 0;

  _CountingBackendClient({
    required this.nearbyPois,
    required this.firstEvents,
    required this.subsequentEvents,
  });

  @override
  Future<List<POI>> fetchNearby({required double lat, required double lon,
    required int radius, required String lang, required String persona}) async => nearbyPois;

  @override
  Stream<NarrationEvent> narrate({required List<POI> candidates, required String persona,
    required String lang, required String length,
    PreviousSelection? previousSelection, bool forceRegenerate = false}) async* {
    callCount++;
    final events = callCount == 1 ? firstEvents : subsequentEvents;
    for (final e in events) yield e;
  }

  @override
  Stream<QaEvent> qa({required Uint8List audioBytes, required String persona,
    required String lang, String? currentPoiId, String narrationSoFar = ''}) async* {}
}
```

Also add imports at the top of the test file:
```dart
import 'dart:typed_data';
import 'package:flutter_app/shared/settings/app_settings.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
```

- [ ] **Step 6.2: Run tests to verify they fail**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart
```
Expected: compilation errors — `appSettingsProvider`, `isWaitingForDisplacement` not defined yet.

- [ ] **Step 6.3: Rewrite trigger_provider.dart with displacement support**

Replace the full contents of `flutter_app/lib/features/narration/providers/trigger_provider.dart`:

```dart
import 'dart:async';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/haversine.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_events.dart';
import 'package:geolocator/geolocator.dart';

class TriggerState {
  final bool isCountingDown;
  final Duration countdownRemaining;
  final bool isWaitingForDisplacement;
  final double? skipLat;
  final double? skipLon;
  final double movedMeters;

  const TriggerState({
    this.isCountingDown = false,
    this.countdownRemaining = Duration.zero,
    this.isWaitingForDisplacement = false,
    this.skipLat,
    this.skipLon,
    this.movedMeters = 0,
  });

  TriggerState copyWith({
    bool? isCountingDown,
    Duration? countdownRemaining,
    bool? isWaitingForDisplacement,
    double? skipLat,
    double? skipLon,
    double? movedMeters,
  }) =>
      TriggerState(
        isCountingDown: isCountingDown ?? this.isCountingDown,
        countdownRemaining: countdownRemaining ?? this.countdownRemaining,
        isWaitingForDisplacement: isWaitingForDisplacement ?? this.isWaitingForDisplacement,
        skipLat: skipLat ?? this.skipLat,
        skipLon: skipLon ?? this.skipLon,
        movedMeters: movedMeters ?? this.movedMeters,
      );
}

class TriggerNotifier extends Notifier<TriggerState> {
  final Set<String> _sessionPlayedIds = {};
  List<POI> _latestPois = [];
  Timer? _cooldownTimer;
  DateTime? _cooldownUntil;
  String? _lastSelectedPoiId;
  String _lastSelectedPoiName = '';
  String _lastScript = '';
  bool _hasEverFired = false;
  StreamSubscription<Position>? _locationSub;

  @override
  TriggerState build() {
    ref.listen<AsyncValue<List<POI>>>(
      poiProvider,
      (_, next) => next.whenData((pois) {
        _latestPois = pois;
        AppLogger.info(LogEvents.triggerEval, {'layer': 'pois_updated', 'count': pois.length});
        if (!_hasEverFired && pois.isNotEmpty && !state.isCountingDown) {
          final narState = ref.read(narrationProvider);
          if (narState.status == NarrationStatus.idle) {
            _doCandidatesRequest().catchError((Object e, StackTrace st) {
              AppLogger.error(LogEvents.apiError, {'context': 'initial_trigger'}, e, st);
            });
          }
        }
      }),
    );

    ref.listen<NarrationState>(
      narrationProvider,
      (prev, next) {
        // Mark POI as played when MetaEvent received
        if (prev?.currentPoi == null && next.currentPoi != null) {
          _sessionPlayedIds.add(next.currentPoi!.id);
          _hasEverFired = true;
        }
        // Start countdown when narration completes normally
        if (prev?.status == NarrationStatus.playing && next.status == NarrationStatus.idle) {
          _lastSelectedPoiId = next.currentPoi?.id;
          _lastSelectedPoiName = next.currentPoi?.name ?? '';
          _lastScript = next.scriptBuffer;
          _startCountdown();
        }
        // Start countdown on error
        if ((prev?.status == NarrationStatus.loading || prev?.status == NarrationStatus.playing) &&
            next.status == NarrationStatus.error) {
          _startCountdown();
        }
        // Handle skip: switch to displacement-wait mode
        if (next.lastEventWasSkip && !(prev?.lastEventWasSkip ?? false)) {
          _handleSkip();
        }
      },
    );

    ref.onDispose(() {
      _cooldownTimer?.cancel();
      _locationSub?.cancel();
    });

    return const TriggerState();
  }

  void _startCountdown() {
    _locationSub?.cancel();
    _locationSub = null;
    _cooldownTimer?.cancel();
    final seconds = ref.read(appSettingsProvider).countdownSeconds;
    final duration = Duration(seconds: seconds);
    _cooldownUntil = DateTime.now().add(duration);
    state = TriggerState(isCountingDown: true, countdownRemaining: duration);

    _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      final remaining = _cooldownUntil!.difference(DateTime.now());
      if (remaining <= Duration.zero) {
        timer.cancel();
        _cooldownTimer = null;
        _cooldownUntil = null;
        state = const TriggerState();
        _doCandidatesRequest().catchError((Object e, StackTrace st) {
          AppLogger.error(LogEvents.apiError, {'context': 'countdown_expired'}, e, st);
        });
      } else {
        state = TriggerState(isCountingDown: true, countdownRemaining: remaining);
      }
    });
  }

  void skipCountdown() {
    _cooldownTimer?.cancel();
    _cooldownTimer = null;
    _cooldownUntil = null;
    state = const TriggerState();
    _doCandidatesRequest().catchError((Object e, StackTrace st) {
      AppLogger.error(LogEvents.apiError, {'context': 'countdown_skip'}, e, st);
    });
  }

  void _handleSkip() {
    _cooldownTimer?.cancel();
    _cooldownTimer = null;
    _cooldownUntil = null;
    AppLogger.info(LogEvents.triggerSkip, {'reason': 'poi_trivial_waiting_displacement'});
    state = const TriggerState(isWaitingForDisplacement: true);
    _startDisplacementWatch();
  }

  void _startDisplacementWatch() {
    _locationSub?.cancel();
    double? originLat;
    double? originLon;

    _locationSub = ref.read(locationServiceProvider).positionStream.listen((pos) {
      if (!state.isWaitingForDisplacement) {
        _locationSub?.cancel();
        _locationSub = null;
        return;
      }
      if (originLat == null) {
        originLat = pos.latitude;
        originLon = pos.longitude;
        state = state.copyWith(skipLat: originLat, skipLon: originLon, movedMeters: 0);
        return;
      }
      final dist = haversine(originLat!, originLon!, pos.latitude, pos.longitude);
      final threshold = ref.read(appSettingsProvider).skipDisplacementM;
      state = state.copyWith(movedMeters: dist);
      if (dist >= threshold) {
        _clearDisplacementWatch();
        _doCandidatesRequest().catchError((Object e, StackTrace st) {
          AppLogger.error(LogEvents.apiError, {'context': 'displacement_trigger'}, e, st);
        });
      }
    });
  }

  void _clearDisplacementWatch() {
    _locationSub?.cancel();
    _locationSub = null;
    state = const TriggerState();
  }

  Future<void> _doCandidatesRequest() async {
    if (_latestPois.isEmpty) return;

    final narState = ref.read(narrationProvider);
    if (narState.status == NarrationStatus.playing ||
        narState.status == NarrationStatus.loading) {
      return;
    }

    final lifecycleState = ref.read(appLifecycleStateProvider);
    if (lifecycleState != AppLifecycleState.resumed) return;

    final db = ref.read(localDbProvider);
    final cooldownIds = <String>{};
    for (final poi in _latestPois) {
      if (await db.isCooldown(poi.id, const Duration(hours: 24))) {
        cooldownIds.add(poi.id);
      }
    }

    final available = _latestPois
        .where((p) => !_sessionPlayedIds.contains(p.id) && !cooldownIds.contains(p.id))
        .toList();

    if (available.isEmpty) {
      AppLogger.info(LogEvents.triggerSkip, {'reason': 'no_candidates_available'});
      return;
    }

    final session = ref.read(sessionProvider);
    final previous = _lastSelectedPoiId != null
        ? PreviousSelection(
            poiId: _lastSelectedPoiId!,
            poiName: _lastSelectedPoiName,
            script: _lastScript,
          )
        : null;

    AppLogger.info(LogEvents.narrationTrigger, {
      'candidate_count': available.length,
      'has_previous': previous != null,
    });

    ref.read(narrationProvider.notifier).narrate(
      candidates: available,
      persona: session.persona,
      lang: session.lang,
      previousSelection: previous,
    );
  }
}

final triggerProvider = NotifierProvider<TriggerNotifier, TriggerState>(
  TriggerNotifier.new,
);
```

- [ ] **Step 6.4: Run trigger provider tests**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart
```
Expected: all 5 tests PASS.

- [ ] **Step 6.5: Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart \
        flutter_app/test/unit/trigger_provider_test.dart
git commit -m "feat(flutter): TriggerProvider displacement watch on poi skip"
```

---

## Task 7: Flutter — CountdownBadge displacement UI

**Files:**
- Modify: `flutter_app/lib/features/narration/widgets/countdown_badge.dart`

- [ ] **Step 7.1: Rewrite CountdownBadge to support displacement state**

Replace the full contents of `flutter_app/lib/features/narration/widgets/countdown_badge.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

class CountdownBadge extends ConsumerWidget {
  const CountdownBadge({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final triggerState = ref.watch(triggerProvider);

    if (triggerState.isWaitingForDisplacement) {
      return _DisplacementBadge(state: triggerState);
    }

    if (!triggerState.isCountingDown) return const SizedBox.shrink();

    final settings = ref.watch(appSettingsProvider);
    final totalMs = settings.countdownSeconds * 1000.0;
    final remaining = triggerState.countdownRemaining;
    final remainingSeconds = remaining.inSeconds;
    final progress = remaining.inMilliseconds / totalMs;

    return GestureDetector(
      onTap: () => ref.read(triggerProvider.notifier).skipCountdown(),
      child: Container(
        width: 72,
        height: 72,
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.7),
          shape: BoxShape.circle,
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            CircularProgressIndicator(
              value: progress.clamp(0.0, 1.0),
              strokeWidth: 3,
              color: Colors.white,
              backgroundColor: Colors.white24,
            ),
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '$remainingSeconds',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const Text(
                  '下一個',
                  style: TextStyle(color: Colors.white70, fontSize: 9),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _DisplacementBadge extends ConsumerWidget {
  final TriggerState state;
  const _DisplacementBadge({required this.state});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(appSettingsProvider);
    final threshold = settings.skipDisplacementM;
    final moved = state.movedMeters;
    final progress = (moved / threshold).clamp(0.0, 1.0);
    final movedKm = (moved / 1000).toStringAsFixed(1);
    final thresholdKm = (threshold / 1000).toStringAsFixed(1);

    return Container(
      width: 72,
      height: 72,
      decoration: BoxDecoration(
        color: Colors.grey.shade800.withValues(alpha: 0.85),
        shape: BoxShape.circle,
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          CircularProgressIndicator(
            value: progress,
            strokeWidth: 3,
            color: Colors.white70,
            backgroundColor: Colors.white24,
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.directions_walk, color: Colors.white70, size: 20),
              Text(
                '$movedKm/$thresholdKm',
                style: const TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold),
              ),
              const Text(
                'km',
                style: TextStyle(color: Colors.white54, fontSize: 7),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 7.2: Verify compilation**

```bash
cd flutter_app && flutter analyze lib/features/narration/widgets/countdown_badge.dart
```
Expected: no errors.

- [ ] **Step 7.3: Commit**

```bash
git add flutter_app/lib/features/narration/widgets/countdown_badge.dart
git commit -m "feat(flutter): CountdownBadge shows displacement progress when waiting for movement"
```

---

## Task 8: Flutter — SettingsScreen + MapScreen navigation

**Files:**
- Create: `flutter_app/lib/features/settings/settings_screen.dart`
- Modify: `flutter_app/lib/features/map/screens/map_screen.dart`

- [ ] **Step 8.1: Create SettingsScreen**

Create `flutter_app/lib/features/settings/settings_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(appSettingsProvider);
    final notifier = ref.read(appSettingsProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: const Text('設定'),
        backgroundColor: const Color(0xFF0F3460),
        foregroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        children: [
          const Text('旁白間隔', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 4),
          const Text('旁白結束後，多久觸發下一段旁白', style: TextStyle(color: Colors.grey, fontSize: 13)),
          Slider(
            value: settings.countdownSeconds.toDouble(),
            min: 30,
            max: 300,
            divisions: 27,
            label: '${settings.countdownSeconds} 秒',
            onChanged: (v) => notifier.setCountdownSeconds(v.round()),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('30 秒', style: TextStyle(color: Colors.grey, fontSize: 12)),
              Text('${settings.countdownSeconds} 秒',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              const Text('300 秒', style: TextStyle(color: Colors.grey, fontSize: 12)),
            ],
          ),
          const SizedBox(height: 32),
          const Text('略過景點後的移動距離', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 4),
          const Text('景點不夠重要時，需要移動多遠才再次觸發',
              style: TextStyle(color: Colors.grey, fontSize: 13)),
          Slider(
            value: settings.skipDisplacementM,
            min: 500,
            max: 5000,
            divisions: 45,
            label: '${(settings.skipDisplacementM / 1000).toStringAsFixed(1)} km',
            onChanged: (v) => notifier.setSkipDisplacement(v),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('500 m', style: TextStyle(color: Colors.grey, fontSize: 12)),
              Text('${(settings.skipDisplacementM / 1000).toStringAsFixed(1)} km',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              const Text('5 km', style: TextStyle(color: Colors.grey, fontSize: 12)),
            ],
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 8.2: Add ⚙️ button to MapScreen AppBar**

In `flutter_app/lib/features/map/screens/map_screen.dart`, add import at top:

```dart
import 'package:flutter_app/features/settings/settings_screen.dart';
```

Then find the `actions:` in `AppBar` and add the settings button before the 結束 button:

```dart
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white),
            tooltip: '設定',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SettingsScreen()),
            ),
          ),
          TextButton(
            onPressed: () async {
              await ref.read(sessionProvider.notifier).stop();
              if (context.mounted) context.pop();
            },
            child: const Text('結束', style: TextStyle(color: Colors.red)),
          ),
        ],
```

- [ ] **Step 8.3: Run full Flutter test suite**

```bash
cd flutter_app && flutter test
```
Expected: all tests PASS.

- [ ] **Step 8.4: Analyze full codebase**

```bash
cd flutter_app && flutter analyze
```
Expected: no errors (warnings about unused imports or similar are acceptable).

- [ ] **Step 8.5: Commit**

```bash
git add flutter_app/lib/features/settings/settings_screen.dart \
        flutter_app/lib/features/map/screens/map_screen.dart
git commit -m "feat(flutter): add SettingsScreen with countdown and displacement sliders"
```

---

## Task 9: Run full test suites + final verification

- [ ] **Step 9.1: Run backend full test suite**

```bash
cd backend && python -m pytest tests/unit/ -v --ignore=tests/unit/test_config.py
```
Expected: all tests PASS.

- [ ] **Step 9.2: Run Flutter full test suite**

```bash
cd flutter_app && flutter test
```
Expected: all tests PASS.

- [ ] **Step 9.3: Manual smoke test checklist**

- [ ] Start backend: `cd backend && uvicorn tour_guide.main:app --reload`
- [ ] Run app: `cd flutter_app && flutter run`
- [ ] Walk near a trivial POI (map sign) → verify badge turns grey with walking icon
- [ ] Walk 1.5km → verify narration re-triggers
- [ ] Open ⚙️ Settings → adjust displacement to 500m → verify badge threshold changes
- [ ] Open ⚙️ Settings → adjust countdown to 30s → verify countdown uses new value
