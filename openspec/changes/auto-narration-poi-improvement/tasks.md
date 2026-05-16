## 1. Remove Flutter Map Markers

- [x] 1.1 Delete `flutter_app/lib/features/map/widgets/poi_marker.dart`
- [x] 1.2 Remove markers-building block and `poi_marker.dart` import from `flutter_app/lib/features/map/screens/map_screen.dart`
- [x] 1.3 Verify Flutter analyze reports no errors referencing `poi_marker` or `poisAsync`

## 2. Relax OSM POI Filter

- [x] 2.1 Add failing unit tests to `backend/tests/unit/test_poi_filter.py` for the new name-based filter rules
- [x] 2.2 Update `backend/src/tour_guide/services/poi_filter.py` to require `name` tag instead of `wikipedia`/`wikidata`
- [x] 2.3 Update stale tests in `test_poi_filter.py` that described the old wikidata requirement
- [x] 2.4 Run all POI filter unit tests and confirm they pass

## 3. Add WikipediaClient.search() Method

- [ ] 3.1 Create `backend/tests/unit/test_wikipedia_client.py` with failing tests for `search()` (title found, no results, zh-TW subdomain mapping, opensearch action params)
- [ ] 3.2 Add `search(query: str, lang: str) -> str | None` method to `backend/src/tour_guide/clients/wikipedia.py`
- [ ] 3.3 Run `test_wikipedia_client.py` and confirm all 4 tests pass

## 4. Create NominatimClient

- [ ] 4.1 Create `backend/tests/unit/test_nominatim_client.py` with failing tests (suburb+city parse, borough fallback, town fallback, network error → None, non-200 → None)
- [ ] 4.2 Create `backend/src/tour_guide/clients/nominatim.py` with `NominatimAddress` dataclass and `NominatimClient.reverse()` method
- [ ] 4.3 Run `test_nominatim_client.py` and confirm all 5 tests pass

## 5. Create WikipediaResolver

- [ ] 5.1 Create `backend/tests/unit/test_wikipedia_resolver.py` with failing tests for all fallback levels (direct match, suburb fallback, suburb skipped when None, city fallback, all-fail → None, Nominatim failure → None)
- [ ] 5.2 Create `backend/src/tour_guide/services/wikipedia_resolver.py` with `WikipediaResolver.resolve()` implementing the 4-level fallback chain
- [ ] 5.3 Run `test_wikipedia_resolver.py` and confirm all tests pass

## 6. Add no_data_context to PersonaConfig

- [ ] 6.1 Add failing tests to `backend/tests/unit/test_persona_loader.py` for `no_data_context` field (present and absent in YAML)
- [ ] 6.2 Add `no_data_context: dict[str, str] = field(default_factory=dict)` to `PersonaConfig` in `backend/src/tour_guide/models/persona.py`
- [ ] 6.3 Update `backend/src/tour_guide/prompts/loader.py` to parse `no_data_context` from YAML (pass `dict(data.get("no_data_context") or {})`)
- [ ] 6.4 Run all persona loader tests and confirm they pass

## 7. Update All 5 Persona YAMLs

- [ ] 7.1 Update `backend/prompts/personas/story_brother.yaml` — append scene-opening rule to `narration_template` and add `no_data_context`
- [ ] 7.2 Update `backend/prompts/personas/history_uncle.yaml` — append historical-sentence opening rule and add `no_data_context`
- [ ] 7.3 Update `backend/prompts/personas/gossip_auntie.yaml` — append conspiratorial-whisper opening rule and add `no_data_context`
- [ ] 7.4 Update `backend/prompts/personas/kid_sister.yaml` — append curious-observation opening rule and add `no_data_context`
- [ ] 7.5 Update `backend/prompts/personas/foodie.yaml` — append sensory-description opening rule and add `no_data_context`
- [ ] 7.6 Run `test_persona_loader.py::TestAllPersonaYamls` and confirm all 5 personas load without errors

## 8. Add No-Data Short-Circuit to NarrationService

- [ ] 8.1 Create `backend/tests/unit/test_narration_service.py` with failing tests (LLM not called when wiki=None, TextEvent uses no_data_context text, LLM called when wiki is present)
- [ ] 8.2 Add `voice_id` assignment before the short-circuit block in `backend/src/tour_guide/services/narration_service.py`
- [ ] 8.3 Add the `if poi.wiki is None` short-circuit block after `MetaEvent` yield and before LLM prompt build
- [ ] 8.4 Remove the now-duplicate `voice_id` assignment from inside step 4 of the LLM pipeline
- [ ] 8.5 Run `test_narration_service.py` and confirm all 3 tests pass

## 9. Update POIService to Use WikipediaResolver

- [ ] 9.1 Add `from tour_guide.services.wikipedia_resolver import WikipediaResolver` import to `backend/src/tour_guide/services/poi_service.py`
- [ ] 9.2 Add optional `resolver: WikipediaResolver | None = None` parameter to `POIService.__init__()`
- [ ] 9.3 Update `_nearby_osm()`: after `filter_poi_nodes()`, sort by distance and slice to the nearest 20 nodes
- [ ] 9.4 Update `_nearby_osm()`: after trying the OSM `wikipedia` tag, call `resolver.resolve()` when `wiki is None` and `resolver is not None`
- [ ] 9.5 Run `tests/integration/test_poi_service.py` and confirm no import errors

## 10. Wire DI in main.py

- [ ] 10.1 Add imports for `NominatimClient` and `WikipediaResolver` to `backend/src/tour_guide/main.py`
- [ ] 10.2 Instantiate `NominatimClient` and `WikipediaResolver` in `create_app()` after `WikipediaClient` is created
- [ ] 10.3 Pass `resolver=wikipedia_resolver` to `POIService(...)` constructor call
- [ ] 10.4 Verify app starts without import errors: `python -c "from tour_guide.main import create_app; ..."`
- [ ] 10.5 Run all backend unit tests and confirm they pass
