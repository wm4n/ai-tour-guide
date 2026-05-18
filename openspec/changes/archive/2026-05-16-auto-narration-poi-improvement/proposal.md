## Why

The current POI pipeline silently drops many real landmarks because it requires both an OSM tourism/historic tag AND a wikidata tag — most nodes have only the former. Compounding this, the Flutter map shows tap-able markers that conflict with the auto-trigger-only product direction, and the LLM narration sometimes opens with greetings instead of scene-action sentences. These three problems reduce the density of narrated POIs, create UX inconsistency, and lower narration quality.

## What Changes

- **Remove Flutter map markers** — Delete the `poi_marker.dart` widget and the markers-building block in `map_screen.dart`. The map shows only the user's location dot; POI triggering remains auto-trigger via distance + cooldown.
- **Relax OSM POI filter** — Change `poi_filter.py` from requiring `(tourism|historic) AND (wikipedia|wikidata)` to requiring `(tourism|historic) AND name`. More landmarks enter the pipeline.
- **Add `WikipediaClient.search()` method** — New opensearch-based lookup that returns the first matching article title for a query string.
- **Add `NominatimClient`** — New lightweight reverse-geocoding client (`nominatim.openstreetmap.org/reverse`) that returns suburb and city for a lat/lon.
- **Add `WikipediaResolver`** — New service with a 4-level Wikipedia fallback chain: (1) search by POI name, (2) search by "name，suburb", (3) search by "name，city", (4) return `None`.
- **Update `POIService`** — Inject `WikipediaResolver`, sort filtered nodes by distance and limit to nearest 20 before Wikipedia lookups, then use resolver when the OSM wikipedia tag yields nothing.
- **Add `no_data_context` to personas** — Each of the 5 persona YAMLs gains an opening-style instruction in `narration_template` and a `no_data_context` verbal fallback phrase for when no Wikipedia data is found.
- **Add `no_data_context` short-circuit in `NarrationService`** — When `poi.wiki is None`, TTS the pre-written `no_data_context` phrase directly and return; the LLM is never called.
- **Add `PersonaConfig.no_data_context` field** — New `dict[str, str]` field with `default_factory=dict` for backward compatibility.

## Capabilities

### New Capabilities

- `wikipedia-resolver`: Multi-level Wikipedia article lookup service (NominatimClient + WikipediaResolver + WikipediaClient.search) that broadens search from POI name → suburb → city before giving up.

### Modified Capabilities

- `poi-map`: Requirement change — map no longer shows POI markers; only the user's real-time location is displayed. Tap-to-narrate is removed entirely.
- `narration-stream`: Requirement change — when no Wikipedia data is available for a POI (`wiki is None`), narration short-circuits to a pre-written persona phrase (TTS only, no LLM call). Narration templates now include persona-specific scene-opening instructions.
- `trigger-engine`: No spec-level requirement change (auto-trigger distance/cooldown logic unchanged).

## Impact

**Backend files:**
- `backend/src/tour_guide/services/poi_filter.py` — filter logic changed
- `backend/src/tour_guide/clients/wikipedia.py` — new `search()` method
- `backend/src/tour_guide/clients/nominatim.py` — new file
- `backend/src/tour_guide/services/wikipedia_resolver.py` — new file
- `backend/src/tour_guide/services/poi_service.py` — injected resolver, 20-node limit
- `backend/src/tour_guide/models/persona.py` — new `no_data_context` field
- `backend/src/tour_guide/prompts/loader.py` — parse `no_data_context` from YAML
- `backend/src/tour_guide/services/narration_service.py` — no-data short-circuit
- `backend/src/tour_guide/main.py` — DI wiring for NominatimClient + WikipediaResolver
- `backend/prompts/personas/*.yaml` (×5) — opening hint + `no_data_context`

**Flutter files:**
- `flutter_app/lib/features/map/screens/map_screen.dart` — remove markers block
- `flutter_app/lib/features/map/widgets/poi_marker.dart` — deleted

**External APIs added:**
- Nominatim OSM reverse geocoding (`nominatim.openstreetmap.org`) — no API key required; `User-Agent` header required by policy
- Wikipedia opensearch API (`/w/api.php?action=opensearch`) — no API key required

**No breaking changes** to the narration HTTP API or Flutter↔backend protocol.
