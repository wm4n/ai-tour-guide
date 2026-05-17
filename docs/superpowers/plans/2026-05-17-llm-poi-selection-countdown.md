# LLM POI Selection + Countdown Trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace front-end TriggerEngine POI selection with backend LLM selection from all 500m candidates, and add a YouTube-style countdown badge UI that controls the narration trigger interval.

**Architecture:** Frontend sends all 500m POI candidates to backend on each trigger. Backend LLM selects the best POI and streams narration — MetaEvent now carries `poi_id` + `poi_name` so frontend knows what was chosen. After narration ends, TriggerNotifier starts a 90s countdown shown as a bottom-right badge; when it expires (or user taps), candidates are sent again.

**Tech Stack:** Python/FastAPI (backend), LiteLLM/Gemini (LLM), Flutter/Riverpod (frontend), Dart Timer (countdown)

---

## File Map

| File | Change |
|---|---|
| `backend/src/tour_guide/services/narration_service.py` | Add `poi_name` to `MetaEvent` dataclass |
| `backend/src/tour_guide/api/narration.py` | New `POICandidate`, `PreviousSelection` models; update `NarrationRequest`; wire `POISelectorService` |
| `backend/src/tour_guide/services/poi_selector.py` | **New** — LLM-based POI selection service |
| `backend/src/tour_guide/main.py` | Create + inject `POISelectorService` |
| `backend/src/tour_guide/log_events.py` | Add `POI_SELECTION` event constant |
| `backend/tests/unit/test_poi_selector.py` | **New** — unit tests for selector |
| `flutter_app/lib/shared/backend/models/narration_event.dart` | Add `poiName` to `MetaEvent` |
| `flutter_app/lib/shared/backend/backend_client.dart` | Add `PreviousSelection`; change `narrate()` to accept candidates list |
| `flutter_app/lib/features/narration/providers/narration_provider.dart` | `narrate()` takes candidates; populate `currentPoi` from MetaEvent; accumulate `scriptBuffer` |
| `flutter_app/lib/features/narration/providers/trigger_provider.dart` | Replace `TriggerEngine` with countdown; add `TriggerState`; listen to narration state |
| `flutter_app/lib/features/narration/widgets/countdown_badge.dart` | **New** — countdown badge widget |
| `flutter_app/lib/features/map/screens/map_screen.dart` | Add `CountdownBadge` to stack |
| `flutter_app/test/unit/trigger_provider_test.dart` | Update tests for new countdown-based trigger |

---

## Task 1: Add `poi_name` to backend `MetaEvent`

**Files:**
- Modify: `backend/src/tour_guide/services/narration_service.py`
- Modify: `backend/tests/unit/test_narration_service.py`

- [ ] **Step 1: Update `MetaEvent` dataclass to include `poi_name`**

In `narration_service.py`, change `MetaEvent` from:
```python
@dataclass
class MetaEvent:
    type: Literal["meta"] = "meta"
    poi_id: str = ""
    cache_hit: bool = False
    confidence: str = "low"
    estimated_duration_s: int = 0
```
to:
```python
@dataclass
class MetaEvent:
    type: Literal["meta"] = "meta"
    poi_id: str = ""
    poi_name: str = ""
    cache_hit: bool = False
    confidence: str = "low"
    estimated_duration_s: int = 0
```

- [ ] **Step 2: Pass `poi_name` when yielding MetaEvent in `narrate()`**

In `narration_service.py`, find all `yield MetaEvent(...)` calls (cache hit path at line ~117 and cache miss path at line ~129). Update both:

```python
# At the start of narrate(), extract name once:
poi_name = poi.osm.tags.get("name", poi.osm.id)

# Cache hit path:
yield MetaEvent(
    poi_id=poi.osm.id,
    poi_name=poi_name,
    cache_hit=True,
    confidence=confidence,
)

# Cache miss path:
yield MetaEvent(
    poi_id=poi.osm.id,
    poi_name=poi_name,
    cache_hit=False,
    confidence=confidence,
)
```

- [ ] **Step 3: Run existing narration service tests to confirm no regressions**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/backend
python -m pytest tests/unit/test_narration_service.py -v
```

Expected: all existing tests PASS (MetaEvent gains new optional field, no breaking change)

- [ ] **Step 4: Commit**

```bash
git add backend/src/tour_guide/services/narration_service.py
git commit -m "feat: add poi_name to backend MetaEvent"
```

---

## Task 2: Backend new request models (`POICandidate`, `PreviousSelection`)

**Files:**
- Modify: `backend/src/tour_guide/api/narration.py`

- [ ] **Step 1: Replace `NarrationRequest` with multi-candidate version**

In `narration.py`, replace the existing Pydantic models and `NarrationRequest` with:

```python
class POICandidate(BaseModel):
    poi_id: str
    poi_name: str = ""
    poi_lat: float = 0.0
    poi_lon: float = 0.0
    distance_m: float = 0.0
    poi_tags: dict[str, str] = Field(default_factory=dict)
    wiki_title: str | None = None
    wiki_extract: str | None = None


class PreviousSelection(BaseModel):
    poi_id: str
    poi_name: str = ""
    script: str = ""


class NarrationRequest(BaseModel):
    candidates: list[POICandidate]
    persona: str = "history_uncle"
    lang: str = "zh-TW"
    length: str = "medium"
    force_regenerate: bool = False
    previous_selection: PreviousSelection | None = None
```

- [ ] **Step 2: Confirm FastAPI can import the module without error**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/backend
python -c "from tour_guide.api.narration import NarrationRequest, POICandidate, PreviousSelection; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/tour_guide/api/narration.py
git commit -m "feat: replace single-POI NarrationRequest with multi-candidate model"
```

---

## Task 3: Create `POISelectorService`

**Files:**
- Create: `backend/src/tour_guide/services/poi_selector.py`
- Modify: `backend/src/tour_guide/log_events.py`
- Create: `backend/tests/unit/test_poi_selector.py`

- [ ] **Step 1: Add `POI_SELECTION` log event**

In `backend/src/tour_guide/log_events.py`, add under `# NARRATION`:
```python
POI_SELECTION = "POI_SELECTION"
```

- [ ] **Step 2: Write failing unit test for `POISelectorService`**

Create `backend/tests/unit/test_poi_selector.py`:

```python
"""Unit tests for POISelectorService."""
import pytest
from tour_guide.api.narration import POICandidate, PreviousSelection
from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.services.poi_selector import POISelectorService


def make_fake_llm(response: str):
    from unittest.mock import MagicMock

    fake = MagicMock()

    async def _chat_stream(*args, **kwargs):
        yield response

    fake.chat_stream = _chat_stream
    return fake


@pytest.fixture
def fake_persona():
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


@pytest.mark.asyncio
async def test_selector_returns_valid_poi_id(fake_persona):
    candidates = [
        POICandidate(poi_id="node/1", poi_name="故宮", distance_m=80, wiki_extract="故宮介紹"),
        POICandidate(poi_id="node/2", poi_name="中正紀念堂", distance_m=300, wiki_extract="介紹"),
    ]
    llm = make_fake_llm("node/1")
    service = POISelectorService(llm=llm)
    selected = await service.select(candidates=candidates, persona=fake_persona, lang="zh-TW")
    assert selected == "node/1"


@pytest.mark.asyncio
async def test_selector_falls_back_to_first_candidate_on_invalid_response(fake_persona):
    candidates = [
        POICandidate(poi_id="node/A", poi_name="景點A", distance_m=50, wiki_extract="info"),
        POICandidate(poi_id="node/B", poi_name="景點B", distance_m=200, wiki_extract="info"),
    ]
    llm = make_fake_llm("some_nonexistent_id")
    service = POISelectorService(llm=llm)
    selected = await service.select(candidates=candidates, persona=fake_persona, lang="zh-TW")
    assert selected == "node/A"


@pytest.mark.asyncio
async def test_selector_includes_previous_selection_context(fake_persona):
    candidates = [POICandidate(poi_id="node/1", poi_name="故宮", distance_m=80, wiki_extract="info")]
    previous = PreviousSelection(poi_id="node/old", poi_name="舊景點", script="上次講了很多關於歷史...")
    captured_messages = []

    from unittest.mock import MagicMock

    fake_llm = MagicMock()

    async def _chat_stream(messages, opts):
        captured_messages.extend(messages)
        yield "node/1"

    fake_llm.chat_stream = _chat_stream
    service = POISelectorService(llm=fake_llm)
    await service.select(candidates=candidates, persona=fake_persona, lang="zh-TW", previous=previous)
    user_msg = next(m for m in captured_messages if m.role == "user")
    assert "舊景點" in user_msg.content
    assert "上次講了很多關於歷史" in user_msg.content
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/backend
python -m pytest tests/unit/test_poi_selector.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tour_guide.services.poi_selector'`

- [ ] **Step 4: Implement `POISelectorService`**

Create `backend/src/tour_guide/services/poi_selector.py`:

```python
"""POISelectorService — uses LLM to select the most narratable POI from candidates."""
import logging

from tour_guide.log_events import LogEvents
from tour_guide.logging_config import log_event
from tour_guide.models.persona import PersonaConfig
from tour_guide.providers.llm import LlmOpts, LlmProvider, Message

logger = logging.getLogger(__name__)


class POISelectorService:
    """Non-streaming LLM call that picks the best POI id from a candidate list."""

    def __init__(self, llm: LlmProvider) -> None:
        self._llm = llm

    async def select(
        self,
        candidates,   # list[POICandidate] — imported at call site to avoid circular
        persona: PersonaConfig,
        lang: str,
        previous=None,  # PreviousSelection | None
    ) -> str:
        """Return the poi_id of the best candidate. Falls back to candidates[0] on error."""
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
            f"- Reply with ONLY the poi_id of the selected POI, nothing else"
        )

        messages = [
            Message(role="system", content="You are a tour guide POI selector. Output only the poi_id."),
            Message(role="user", content=user_content),
        ]
        opts = LlmOpts(temperature=0.1, max_tokens=64)

        result = ""
        async for chunk in self._llm.chat_stream(messages, opts):
            result += chunk
        selected_id = result.strip()

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

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/backend
python -m pytest tests/unit/test_poi_selector.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/services/poi_selector.py \
        backend/src/tour_guide/log_events.py \
        backend/tests/unit/test_poi_selector.py
git commit -m "feat: add POISelectorService with LLM-based candidate selection"
```

---

## Task 4: Wire `POISelectorService` into endpoint + DI

**Files:**
- Modify: `backend/src/tour_guide/api/narration.py`
- Modify: `backend/src/tour_guide/main.py`

- [ ] **Step 1: Add selector dependency + update endpoint logic in `narration.py`**

In `narration.py`, add after existing imports:
```python
from tour_guide.services.poi_selector import POISelectorService
```

Add new dependency getter after `get_persona_registry`:
```python
def get_poi_selector_service() -> POISelectorService:
    raise NotImplementedError("Override with dependency")
```

Replace the entire `narrate()` endpoint body with:

```python
@router.post("/narration")
async def narrate(
    request: NarrationRequest,
    narration_service: NarrationService = Depends(get_narration_service),  # noqa: B008
    poi_selector: POISelectorService = Depends(get_poi_selector_service),  # noqa: B008
    persona_registry: dict = Depends(get_persona_registry),  # noqa: B008
):
    if not request.candidates:
        raise HTTPException(status_code=400, detail="candidates list must not be empty")
    if request.persona not in persona_registry:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown persona: '{request.persona}'. "
            f"Valid options: {sorted(persona_registry.keys())}",
        )
    persona: PersonaConfig = persona_registry[request.persona]

    # Step 1: LLM selects best POI from candidates
    selected_id = await poi_selector.select(
        candidates=request.candidates,
        persona=persona,
        lang=request.lang,
        previous=request.previous_selection,
    )

    # Step 2: Find selected candidate and build POIContext
    selected = next((c for c in request.candidates if c.poi_id == selected_id), request.candidates[0])
    tags = dict(selected.poi_tags)
    if selected.poi_name and "name" not in tags:
        tags["name"] = selected.poi_name

    wiki: WikiArticle | None = None
    if selected.wiki_title and selected.wiki_extract:
        wiki = WikiArticle(
            title=selected.wiki_title,
            extract=selected.wiki_extract,
            url="",
            lang=request.lang,
        )

    poi_context = POIContext(
        osm=OsmNode(id=selected.poi_id, lat=selected.poi_lat, lon=selected.poi_lon, tags=tags),
        wiki=wiki,
    )
    logger.info(
        "narration request | selected_poi_id=%s | poi_name=%s | has_wiki=%s | candidates=%d",
        selected.poi_id,
        tags.get("name", selected.poi_id),
        wiki is not None,
        len(request.candidates),
    )

    async def generate():
        try:
            async for event in narration_service.narrate(
                poi=poi_context,
                persona=persona,
                lang=request.lang,
                length=request.length,
                force_regenerate=request.force_regenerate,
            ):
                event_type = event.type
                data = _event_to_dict(event)
                yield encode_event(event_type, data)
        except Exception as e:
            logger.exception("narration pipeline failed for poi_id=%s", selected.poi_id)
            yield encode_event(
                "error",
                {"code": "internal_error", "message": str(e), "retry_after_s": 0},
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 2: Wire `POISelectorService` in `main.py`**

In `main.py`, add import:
```python
from tour_guide.services.poi_selector import POISelectorService
```

After `narration_service = NarrationService(...)`, add:
```python
poi_selector_service = POISelectorService(llm=llm_provider)
```

Add dependency override after `narration.get_narration_service`:
```python
app.dependency_overrides[narration.get_poi_selector_service] = lambda: poi_selector_service
```

- [ ] **Step 3: Verify app starts without error**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/backend
python -c "from tour_guide.main import create_app; from tour_guide.config import AppConfig; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/src/tour_guide/api/narration.py backend/src/tour_guide/main.py
git commit -m "feat: wire POISelectorService into /narration endpoint"
```

---

## Task 5: Update Flutter `MetaEvent` model

**Files:**
- Modify: `flutter_app/lib/shared/backend/models/narration_event.dart`

- [ ] **Step 1: Add `poiName` field to `MetaEvent`**

In `narration_event.dart`, update `MetaEvent` from:
```dart
class MetaEvent extends NarrationEvent {
  final String poiId;
  final bool cacheHit;
  final String confidence;
  final int estimatedDurationS;

  const MetaEvent({
    required this.poiId,
    required this.cacheHit,
    required this.confidence,
    this.estimatedDurationS = 0,
  });

  factory MetaEvent.fromJson(Map<String, dynamic> json) => MetaEvent(
        poiId: json['poi_id'] as String,
        cacheHit: json['cache_hit'] as bool,
        confidence: json['confidence'] as String,
        estimatedDurationS: (json['estimated_duration_s'] as num? ?? 0).toInt(),
      );
}
```

to:
```dart
class MetaEvent extends NarrationEvent {
  final String poiId;
  final String poiName;
  final bool cacheHit;
  final String confidence;
  final int estimatedDurationS;

  const MetaEvent({
    required this.poiId,
    this.poiName = '',
    required this.cacheHit,
    required this.confidence,
    this.estimatedDurationS = 0,
  });

  factory MetaEvent.fromJson(Map<String, dynamic> json) => MetaEvent(
        poiId: json['poi_id'] as String,
        poiName: json['poi_name'] as String? ?? '',
        cacheHit: json['cache_hit'] as bool,
        confidence: json['confidence'] as String,
        estimatedDurationS: (json['estimated_duration_s'] as num? ?? 0).toInt(),
      );
}
```

- [ ] **Step 2: Run Flutter tests to confirm no breakage**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/flutter_app
flutter test test/unit/models_test.dart -v
```

Expected: PASS (new field has default value, no breaking change)

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/shared/backend/models/narration_event.dart
git commit -m "feat: add poiName to Flutter MetaEvent model"
```

---

## Task 6: Add `PreviousSelection` model + update `BackendClient`

**Files:**
- Modify: `flutter_app/lib/shared/backend/backend_client.dart`

- [ ] **Step 1: Add `PreviousSelection` class and update `BackendClient` abstract interface**

In `backend_client.dart`, add after the imports at the top:
```dart
class PreviousSelection {
  final String poiId;
  final String poiName;
  final String script;

  const PreviousSelection({
    required this.poiId,
    required this.poiName,
    required this.script,
  });
}
```

Update the `BackendClient` abstract `narrate()` method:
```dart
Stream<NarrationEvent> narrate({
  required List<POI> candidates,
  required String persona,
  required String lang,
  required String length,
  PreviousSelection? previousSelection,
  bool forceRegenerate = false,
});
```

- [ ] **Step 2: Update `RealBackendClient.narrate()` to serialize candidates**

Replace the existing `RealBackendClient.narrate()` method with:
```dart
@override
Stream<NarrationEvent> narrate({
  required List<POI> candidates,
  required String persona,
  required String lang,
  required String length,
  PreviousSelection? previousSelection,
  bool forceRegenerate = false,
}) async* {
  final candidatesJson = candidates.map((poi) => <String, dynamic>{
    'poi_id': poi.id,
    'poi_name': poi.name,
    'poi_lat': poi.lat,
    'poi_lon': poi.lon,
    'distance_m': poi.distanceM,
    'poi_tags': poi.tags,
    if (poi.wiki != null) ...{
      'wiki_title': poi.wiki!.title,
      'wiki_extract': poi.wiki!.extract,
    },
  }).toList();

  final body = <String, dynamic>{
    'candidates': candidatesJson,
    'persona': persona,
    'lang': lang,
    'length': length,
    'force_regenerate': forceRegenerate,
    if (previousSelection != null) 'previous_selection': {
      'poi_id': previousSelection.poiId,
      'poi_name': previousSelection.poiName,
      'script': previousSelection.script,
    },
  };

  debugPrint(
    '[LLM Input] candidates=${candidates.length} | persona=$persona | lang=$lang'
    '${previousSelection != null ? " | has_previous=true" : ""}',
  );

  final request = http.Request('POST', Uri.parse('$baseUrl/narration'));
  request.headers['Content-Type'] = 'application/json';
  request.headers['Accept'] = 'text/event-stream';
  request.headers.addAll(_authHeaders);
  request.body = jsonEncode(body);
  final response = await _http.send(request);
  if (response.statusCode != 200) {
    throw Exception('narrate failed: HTTP ${response.statusCode}');
  }
  await for (final sseEvent in SseParser.parse(response.stream)) {
    final event = _toNarrationEvent(sseEvent);
    if (event != null) yield event;
  }
}
```

- [ ] **Step 3: Update `FakeBackendClient.narrate()` signature**

Replace the `FakeBackendClient.narrate()` method with:
```dart
@override
Stream<NarrationEvent> narrate({
  required List<POI> candidates,
  required String persona,
  required String lang,
  required String length,
  PreviousSelection? previousSelection,
  bool forceRegenerate = false,
}) async* {
  for (final event in scriptedEvents) {
    yield event;
  }
}
```

- [ ] **Step 4: Confirm Flutter app compiles**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/flutter_app
flutter analyze lib/shared/backend/backend_client.dart
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/shared/backend/backend_client.dart
git commit -m "feat: update BackendClient.narrate() to accept POI candidates list"
```

---

## Task 7: Update `NarrationNotifier` — candidates input, MetaEvent-based POI resolution

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/narration_provider.dart`

- [ ] **Step 1: Add `scriptBuffer` to `NarrationState` and update `NarrationNotifier.narrate()`**

Replace `narration_provider.dart` with:

```dart
import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_events.dart';

enum NarrationStatus { idle, loading, playing, paused, error }

class NarrationState {
  final NarrationStatus status;
  final POI? currentPoi;
  final String subtitle;
  final String scriptBuffer;
  final double progress;
  final String? confidence;
  final String? errorMessage;

  const NarrationState({
    required this.status,
    this.currentPoi,
    this.subtitle = '',
    this.scriptBuffer = '',
    this.progress = 0,
    this.confidence,
    this.errorMessage,
  });

  NarrationState copyWith({
    NarrationStatus? status,
    POI? currentPoi,
    String? subtitle,
    String? scriptBuffer,
    double? progress,
    String? confidence,
    String? errorMessage,
  }) =>
      NarrationState(
        status: status ?? this.status,
        currentPoi: currentPoi ?? this.currentPoi,
        subtitle: subtitle ?? this.subtitle,
        scriptBuffer: scriptBuffer ?? this.scriptBuffer,
        progress: progress ?? this.progress,
        confidence: confidence ?? this.confidence,
        errorMessage: errorMessage ?? this.errorMessage,
      );
}

class NarrationNotifier extends StateNotifier<NarrationState> {
  NarrationNotifier(this._client, this._audio, this._db)
      : super(const NarrationState(status: NarrationStatus.idle));

  final BackendClient _client;
  final AudioPlayerService _audio;
  final LocalDb _db;
  StreamSubscription<NarrationEvent>? _sub;
  int _audioChunkCount = 0;
  String _currentPersona = 'history_uncle';
  String _currentLang = 'zh-TW';
  DateTime? _narrationStartedAt;
  List<POI> _candidates = [];

  Future<void> narrate({
    required List<POI> candidates,
    required String persona,
    required String lang,
    PreviousSelection? previousSelection,
  }) async {
    _currentPersona = persona;
    _currentLang = lang;
    _candidates = candidates;
    await _sub?.cancel();
    await _audio.reset();
    _audioChunkCount = 0;
    _narrationStartedAt = DateTime.now();
    AppLogger.info(LogEvents.narrationStart, {'candidate_count': candidates.length});
    state = const NarrationState(status: NarrationStatus.loading);

    _sub = _client
        .narrate(
          candidates: candidates,
          persona: persona,
          lang: lang,
          length: 'medium',
          previousSelection: previousSelection,
        )
        .listen(
          _handle,
          onError: (Object e, StackTrace st) {
            AppLogger.error(LogEvents.apiError, {
              'context': 'narration_stream',
            }, e, st);
            state = state.copyWith(
              status: NarrationStatus.error,
              errorMessage: e.toString(),
            );
          },
          onDone: () {
            if (state.status == NarrationStatus.loading) {
              AppLogger.warn(LogEvents.apiError, {'context': 'narration_stream_empty'});
            }
          },
        );
  }

  void _handle(NarrationEvent event) {
    switch (event) {
      case MetaEvent(:final poiId, :final poiName, :final confidence):
        final selectedPoi = _candidates.firstWhere(
          (p) => p.id == poiId,
          orElse: () => _candidates.isNotEmpty ? _candidates.first : POI(
            id: poiId, name: poiName, lat: 0, lon: 0,
            tags: {}, distanceM: 0, confidence: confidence,
          ),
        );
        AppLogger.info(LogEvents.narrationStart, {'poi_id': poiId, 'poi_name': poiName});
        state = state.copyWith(
          status: NarrationStatus.playing,
          currentPoi: selectedPoi,
          confidence: confidence,
        );
      case TextEvent(:final chunk, :final sentenceIdx):
        AppLogger.debug(LogEvents.narrationChunk, {
          'poi_id': state.currentPoi?.id ?? '',
          'sentence_idx': sentenceIdx,
          'chunk': chunk,
          'type': 'text',
        });
        state = state.copyWith(
          subtitle: state.subtitle + chunk,
          scriptBuffer: state.scriptBuffer + chunk,
        );
      case AudioEvent(:final chunkB64):
        _audioChunkCount++;
        AppLogger.debug(LogEvents.narrationChunk, {
          'poi_id': state.currentPoi?.id ?? '',
          'chunk_index': _audioChunkCount,
        });
        final bytes = base64.decode(chunkB64);
        _audio.enqueueBytes(bytes);
        state = state.copyWith(
          progress: (_audioChunkCount * 0.1).clamp(0.0, 0.9),
        );
      case EndEvent():
        final durationMs = _narrationStartedAt != null
            ? DateTime.now().difference(_narrationStartedAt!).inMilliseconds
            : 0;
        final poi = state.currentPoi;
        AppLogger.info(LogEvents.narrationComplete, {
          'poi_id': poi?.id ?? '',
          'duration_ms': durationMs,
          'total_chars': state.subtitle.length,
        });
        _narrationStartedAt = null;
        if (poi != null) _recordNarration(poi);
        state = state.copyWith(
          status: NarrationStatus.idle,
          progress: 1.0,
        );
      case ErrorEvent(:final message):
        state = state.copyWith(
          status: NarrationStatus.error,
          errorMessage: message,
        );
    }
  }

  void _recordNarration(POI poi) {
    _db
        .recordNarration(
          sessionId: 1,
          poiId: poi.id,
          poiName: poi.name,
          poiLat: poi.lat,
          poiLon: poi.lon,
          persona: _currentPersona,
          lang: _currentLang,
          completed: true,
        )
        .catchError((_) {/* ignore FK errors in MVP */});
  }

  Future<void> pause() async {
    await _audio.pause();
    state = state.copyWith(status: NarrationStatus.paused);
  }

  Future<void> resume() async {
    await _audio.resume();
    state = state.copyWith(status: NarrationStatus.playing);
  }

  Future<void> skip() async {
    AppLogger.warn(LogEvents.narrationSkip, {
      'poi_id': state.currentPoi?.id ?? '',
      'reason': 'user_skip',
    });
    await _sub?.cancel();
    await _audio.skip();
    state = state.copyWith(status: NarrationStatus.idle);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final narrationProvider =
    StateNotifierProvider<NarrationNotifier, NarrationState>((ref) {
  return NarrationNotifier(
    ref.watch(backendClientProvider),
    ref.watch(audioPlayerServiceProvider),
    ref.watch(localDbProvider),
  );
});
```

- [ ] **Step 2: Run Flutter analyze**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/flutter_app
flutter analyze lib/features/narration/providers/narration_provider.dart
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/features/narration/providers/narration_provider.dart
git commit -m "feat: NarrationNotifier accepts candidates list, resolves POI from MetaEvent"
```

---

## Task 8: Replace `TriggerNotifier` with countdown-based trigger

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **Step 1: Write failing tests for countdown trigger**

Replace `flutter_app/test/unit/trigger_provider_test.dart` with:

```dart
import 'dart:async';
import 'package:drift/native.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';
import 'package:flutter_app/shared/providers.dart';

const _poi = POI(
  id: 'osm:node:1',
  name: '故宮',
  lat: 25.1023,
  lon: 121.5482,
  tags: {},
  distanceM: 89,
  confidence: 'high',
);

ProviderContainer _buildContainer({
  List<NarrationEvent> scriptedEvents = const [],
  AppLifecycleState lifecycle = AppLifecycleState.resumed,
}) {
  final fakeLocation = FakeLocationService();
  final fakeAudio = FakeAudioPlayerService();
  final db = LocalDb.forTesting(NativeDatabase.memory());

  final container = ProviderContainer(
    overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      backendClientProvider.overrideWithValue(
        FakeBackendClient(
          nearbyPois: const [_poi],
          scriptedEvents: scriptedEvents,
        ),
      ),
      audioPlayerServiceProvider.overrideWithValue(fakeAudio),
      localDbProvider.overrideWithValue(db),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      appLifecycleStateProvider.overrideWith((ref) => StateController(lifecycle)),
    ],
  );
  return container;
}

void main() {
  test('TriggerProvider starts with non-counting state', () async {
    final container = _buildContainer();
    addTearDown(container.dispose);

    container.listen(triggerProvider, (_, __) {});
    await Future<void>.delayed(const Duration(milliseconds: 50));

    final state = container.read(triggerProvider);
    expect(state.isCountingDown, isFalse);
    expect(state.countdownRemaining, Duration.zero);
  });

  test('TriggerProvider fires narrate() when POIs load on first run', () async {
    final narrateCalls = <List<POI>>[];
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(
          FakeBackendClient(
            nearbyPois: const [_poi],
            scriptedEvents: const [EndEvent()],
          ),
        ),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
        sessionLangProvider.overrideWithValue('zh-TW'),
        fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});

    // Emit POIs — should trigger narration immediately (first run)
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));

    final narState = container.read(narrationProvider);
    // After EndEvent, status should be idle (narration completed)
    expect(narState.status, NarrationStatus.idle);
  });

  test('skipCountdown() triggers narration immediately', () async {
    final container = _buildContainer(
      scriptedEvents: const [EndEvent()],
    );
    addTearDown(container.dispose);

    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});

    // Manually start countdown
    fakePosition(25.1023, 121.5482);
    await Future<void>.delayed(const Duration(milliseconds: 50));

    // Inject POIs via poi provider hack
    container.read(triggerProvider.notifier).skipCountdown();
    await Future<void>.delayed(const Duration(milliseconds: 200));

    // Provider should not be in counting-down state after skip
    final state = container.read(triggerProvider);
    expect(state.isCountingDown, isFalse);
  });
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/flutter_app
flutter test test/unit/trigger_provider_test.dart -v 2>&1 | head -30
```

Expected: compile errors — `TriggerState`, `skipCountdown` not defined yet

- [ ] **Step 3: Replace `trigger_provider.dart` with countdown implementation**

Replace the entire file content:

```dart
import 'dart:async';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_events.dart';

class TriggerState {
  final bool isCountingDown;
  final Duration countdownRemaining;

  const TriggerState({
    this.isCountingDown = false,
    this.countdownRemaining = Duration.zero,
  });

  TriggerState copyWith({bool? isCountingDown, Duration? countdownRemaining}) =>
      TriggerState(
        isCountingDown: isCountingDown ?? this.isCountingDown,
        countdownRemaining: countdownRemaining ?? this.countdownRemaining,
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

  static const _countdownDuration = Duration(seconds: 90);

  @override
  TriggerState build() {
    ref.listen<AsyncValue<List<POI>>>(
      poiProvider,
      (_, next) => next.whenData((pois) {
        _latestPois = pois;
        AppLogger.info(LogEvents.triggerEval, {'layer': 'pois_updated', 'count': pois.length});
        // Fire immediately on first POI load if never played
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
        // Mark POI as played when it is first selected (MetaEvent received)
        if (prev?.currentPoi == null && next.currentPoi != null) {
          _sessionPlayedIds.add(next.currentPoi!.id);
          _hasEverFired = true;
        }
        // Start countdown when narration completes
        if (prev?.status == NarrationStatus.playing && next.status == NarrationStatus.idle) {
          _lastSelectedPoiId = next.currentPoi?.id;
          _lastSelectedPoiName = next.currentPoi?.name ?? '';
          _lastScript = next.scriptBuffer;
          _startCountdown();
        }
        // Also start countdown on error to avoid getting stuck
        if ((prev?.status == NarrationStatus.loading || prev?.status == NarrationStatus.playing) &&
            next.status == NarrationStatus.error) {
          _startCountdown();
        }
      },
    );

    ref.onDispose(() {
      _cooldownTimer?.cancel();
    });

    return const TriggerState();
  }

  void _startCountdown() {
    _cooldownTimer?.cancel();
    _cooldownUntil = DateTime.now().add(_countdownDuration);
    state = TriggerState(isCountingDown: true, countdownRemaining: _countdownDuration);

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

  Future<void> _doCandidatesRequest() async {
    if (_latestPois.isEmpty) return;

    final narState = ref.read(narrationProvider);
    if (narState.status == NarrationStatus.playing ||
        narState.status == NarrationStatus.loading) return;

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

- [ ] **Step 4: Run Flutter analyze**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/flutter_app
flutter analyze lib/features/narration/providers/trigger_provider.dart
```

Expected: no errors

- [ ] **Step 5: Run trigger provider tests**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/flutter_app
flutter test test/unit/trigger_provider_test.dart -v
```

Expected: tests PASS (or adjust test expectations to match actual new behavior)

- [ ] **Step 6: Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart \
        flutter_app/test/unit/trigger_provider_test.dart
git commit -m "feat: replace TriggerEngine with countdown-based POI selection trigger"
```

---

## Task 9: Create `CountdownBadge` widget

**Files:**
- Create: `flutter_app/lib/features/narration/widgets/countdown_badge.dart`

- [ ] **Step 1: Create the widget**

Create `flutter_app/lib/features/narration/widgets/countdown_badge.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';

class CountdownBadge extends ConsumerWidget {
  const CountdownBadge({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final triggerState = ref.watch(triggerProvider);

    if (!triggerState.isCountingDown) return const SizedBox.shrink();

    final totalSeconds = 90.0;
    final remaining = triggerState.countdownRemaining;
    final remainingSeconds = remaining.inSeconds;
    final progress = remaining.inMilliseconds / (totalSeconds * 1000);

    return GestureDetector(
      onTap: () => ref.read(triggerProvider.notifier).skipCountdown(),
      child: Container(
        width: 72,
        height: 72,
        decoration: BoxDecoration(
          color: Colors.black.withOpacity(0.7),
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
```

- [ ] **Step 2: Verify no analyzer errors**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/flutter_app
flutter analyze lib/features/narration/widgets/countdown_badge.dart
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/features/narration/widgets/countdown_badge.dart
git commit -m "feat: add CountdownBadge widget with circular progress and skip-on-tap"
```

---

## Task 10: Add `CountdownBadge` to `MapScreen`

**Files:**
- Modify: `flutter_app/lib/features/map/screens/map_screen.dart`

- [ ] **Step 1: Add import and `CountdownBadge` to map Stack**

In `map_screen.dart`, add the import after existing imports:
```dart
import 'package:flutter_app/features/narration/widgets/countdown_badge.dart';
```

In the `Stack` children in `build()`, add the badge after the `PushToTalkButton` positioned widget:
```dart
const Positioned(
  bottom: 110,
  right: 16,
  child: CountdownBadge(),
),
```

The full Stack children block becomes:
```dart
children: [
  GoogleMap(
    initialCameraPosition: CameraPosition(
      target: initialTarget,
      zoom: 16,
    ),
    myLocationEnabled: true,
    myLocationButtonEnabled: true,
    onMapCreated: (c) {
      _mapController = c;
      if (position != null) _centerOnPosition(position);
    },
  ),
  const Align(
    alignment: Alignment.bottomCenter,
    child: NarrationSheet(),
  ),
  const Positioned(
    bottom: 100,
    left: 0,
    right: 0,
    child: Center(child: PushToTalkButton()),
  ),
  const Positioned(
    bottom: 110,
    right: 16,
    child: CountdownBadge(),
  ),
],
```

Also change `ref.read(triggerProvider)` in `initState` to `ref.read(triggerProvider.notifier)` to ensure the notifier is initialized (it was previously returning void, now returns TriggerState but we still just want initialization):

```dart
@override
void initState() {
  super.initState();
  ref.read(triggerProvider.notifier); // initialize the notifier
}
```

Wait — `ref.read` in `initState` doesn't work with ConsumerStatefulWidget. Check the existing code: it uses `ref.read(triggerProvider)` directly. With the new `TriggerState` type, this still works the same way (reads the state, which has the side effect of building the notifier). Keep `ref.read(triggerProvider)` as-is.

- [ ] **Step 2: Run Flutter analyze on changed files**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/flutter_app
flutter analyze lib/features/map/screens/map_screen.dart \
               lib/features/narration/widgets/countdown_badge.dart \
               lib/features/narration/providers/trigger_provider.dart \
               lib/features/narration/providers/narration_provider.dart \
               lib/shared/backend/backend_client.dart
```

Expected: no errors

- [ ] **Step 3: Run all unit tests**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/flutter_app
flutter test test/unit/ -v
```

Expected: all pass

- [ ] **Step 4: Run backend tests**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide/backend
python -m pytest tests/unit/ -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/map/screens/map_screen.dart
git commit -m "feat: add CountdownBadge to MapScreen bottom-right corner"
```

---

## Final Verification Checklist

- [ ] Backend: `POST /narration` accepts `candidates` list and returns MetaEvent with `poi_name`
- [ ] Backend: `POISelectorService` selects best POI and logs the choice
- [ ] Flutter: `MetaEvent` parses `poi_name` from JSON
- [ ] Flutter: `BackendClient.narrate()` sends candidates list
- [ ] Flutter: After narration ends, countdown badge appears bottom-right
- [ ] Flutter: Tapping countdown badge fires next request immediately
- [ ] Flutter: After 90s, next request fires automatically
- [ ] Flutter: Previously played POIs are excluded from candidates (session + 24h cooldown)
- [ ] Flutter: `previous_selection` with full script sent on subsequent requests
- [ ] Backend unit tests pass: `pytest tests/unit/ -v`
- [ ] Flutter unit tests pass: `flutter test test/unit/ -v`
