## 1. Project Skeleton & Tooling

- [x] 1.1 Create `backend/pyproject.toml` with PEP 621 project definition, all runtime and dev dependencies (fastapi, uvicorn, sse-starlette, pydantic-settings, httpx, litellm, google-genai, PyYAML, aiofiles, pytest, pytest-asyncio, ruff, respx, freezegun)
- [x] 1.2 Create `backend/ruff.toml` linter config (target py312, line-length 100, select E/F/I/B/UP/ASYNC/S/RUF)
- [x] 1.3 Create `backend/pytest.ini` with `asyncio_mode = auto` and `real_provider` marker registered
- [x] 1.4 Create `backend/.env.example` with GEMINI_API_KEY, HOST, PORT, POI_CACHE_DIR, NARRATION_CACHE_DIR
- [x] 1.5 Create `backend/README.md` with setup steps, run command, test command, curl recipes for all 3 endpoints
- [x] 1.6 Create empty package files: `src/tour_guide/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/smoke/__init__.py`
- [x] 1.7 Create `backend/tests/conftest.py` (empty placeholder)
- [x] 1.8 Install dependencies with `pip install -e ".[dev]"` and verify `pytest --version` succeeds

## 2. First Passing Test

- [x] 2.1 Create `tests/unit/test_smoke.py` with `test_python_works` (assert 1+1==2) and run `pytest tests/unit/test_smoke.py -v` to confirm pytest works

## 3. SentenceSplitter (Pure Function, TDD)

- [x] 3.1 Write failing tests in `tests/unit/test_sentence_splitter.py` covering Chinese punctuation split, English punctuation split, mixed text, and edge cases (empty string, no punctuation)
- [x] 3.2 Create `src/tour_guide/pipeline/__init__.py` and implement `split_complete_text(text: str) -> list[str]` in `sentence_splitter.py` to pass basic tests
- [x] 3.3 Write failing tests for `StreamingSentenceBuffer` covering chunk-by-chunk feeding, sentence yielding on punctuation detection, and `flush()` for remaining buffer
- [x] 3.4 Implement `StreamingSentenceBuffer` class in `sentence_splitter.py` to pass all streaming tests

## 4. Data Models

- [ ] 4.1 Create `src/tour_guide/models/__init__.py` and `models/poi.py` with `OsmNode`, `WikiArticle`, `POIContext`, `POI`, `BBox`, `TagFilter` dataclasses
- [ ] 4.2 Create `models/persona.py` with `PersonaConfig`, `VoiceStyle`, `StyleProfile` dataclasses matching YAML schema
- [ ] 4.3 Write unit tests in `tests/unit/test_poi_models.py` verifying field types and defaults

## 5. PersonaLoader (YAML, TDD)

- [ ] 5.1 Write failing tests in `tests/unit/test_persona_loader.py` covering valid YAML load, missing file error, and invalid schema error
- [ ] 5.2 Create `src/tour_guide/prompts/__init__.py`, `prompts/loader.py` with `PersonaLoader.load(persona_id: str) -> PersonaConfig` reading from `prompts/personas/`
- [ ] 5.3 Create `backend/prompts/personas/history_uncle.yaml` with full persona definition: id, display_name, voice (Charon), voice_style (speaking_rate 0.95), style_profile (embellishment 0.1), system_prompt, narration_template, qa_template, system_messages, confidence_labels
- [ ] 5.4 Run persona loader tests and confirm all pass

## 6. PromptBuilder (Pure Function, TDD)

- [ ] 6.1 Write failing tests in `tests/unit/test_prompt_builder.py` covering: messages contain system + user roles, POI name appears in prompt, wiki content included when available, wiki extract truncated at 1500 chars
- [ ] 6.2 Create `prompts/builder.py` with `PromptBuilder.build(persona, poi, lang, length) -> list[Message]` composing from persona `narration_template`
- [ ] 6.3 Run all prompt builder tests and confirm pass

## 7. ConfidenceClassifier (Pure Function, TDD)

- [ ] 7.1 Write failing tests in `tests/unit/test_confidence.py` for high (wiki >=200 chars), medium (wiki <200 chars), low (no wiki)
- [ ] 7.2 Create `src/tour_guide/services/confidence.py` with `ConfidenceClassifier.classify(poi_context) -> Literal["high","medium","low"]`
- [ ] 7.3 Run confidence tests and confirm pass

## 8. Provider Interfaces and Fakes

- [ ] 8.1 Create `src/tour_guide/providers/__init__.py` and `providers/llm.py` with `LlmProvider` Protocol, `LlmOpts`, `Message` types
- [ ] 8.2 Write failing tests in `tests/unit/test_llm_provider.py` for `FakeLlmProvider` yielding scripted chunks in order
- [ ] 8.3 Create `providers/fakes.py` with `FakeLlmProvider(scripted_chunks: list[str])` implementing `LlmProvider`
- [ ] 8.4 Create `providers/tts.py` with `TtsProvider` Protocol and `TtsOpts`
- [ ] 8.5 Write failing tests in `tests/unit/test_tts_provider.py` for `FakeTtsProvider` returning fixed silent bytes
- [ ] 8.6 Add `FakeTtsProvider` to `providers/fakes.py` implementing `TtsProvider`

## 9. NarrationService (Integration, TDD)

- [ ] 9.1 Write failing integration tests in `tests/integration/test_narration_service.py` covering: cache miss runs full pipeline, cache hit returns audio directly, force_regenerate bypasses cache, completed narration is saved to cache; use FakeLlmProvider and FakeTtsProvider
- [ ] 9.2 Create `src/tour_guide/services/__init__.py` and `services/narration_service.py` with `NarrationService.narrate()` orchestrating PromptBuilder → LlmProvider → SentenceSplitter → TtsProvider → yield NarrationEvent
- [ ] 9.3 Define `NarrationEvent` type variants: `MetaEvent`, `TextEvent`, `AudioEvent`, `EndEvent`, `ErrorEvent`
- [ ] 9.4 Run narration service integration tests and confirm all pass

## 10. External HTTP Clients (TDD with respx)

- [ ] 10.1 Write failing tests in `tests/integration/test_wikipedia_client.py` using respx to mock Wikipedia REST API; cover known title returns WikiArticle, unknown returns None, disambiguation returns None
- [ ] 10.2 Create `src/tour_guide/clients/__init__.py` and `clients/wikipedia.py` with `WikipediaClient.summary(title, lang) -> WikiArticle | None` using httpx
- [ ] 10.3 Write failing tests in `tests/integration/test_overpass_client.py` using respx; cover successful query, 503 retry, 429 raises OverpassRateLimitError
- [ ] 10.4 Create `clients/overpass.py` with `OverpassClient.query(bbox, tags) -> list[OsmNode]` with retry (3 attempts, 1s/2s/4s backoff)

## 11. POI Filter Logic (Pure Function, TDD)

- [ ] 11.1 Write failing tests in `tests/unit/test_poi_filter.py` covering: node with tourism tag + wiki tag passes, node without wiki tag excluded, node with excluded tag type excluded
- [ ] 11.2 Create POI filter function (in `services/poi_service.py` or dedicated `services/poi_filter.py`) with tourism/historic whitelist and wiki tag requirement

## 12. POI Cache (Filesystem, TDD)

- [ ] 12.1 Write failing tests in `tests/unit/test_poi_cache.py` covering: cache hit returns stored value, cache miss returns None, expired TTL treated as miss, LRU eviction at 100 MB; use `tmp_path` pytest fixture
- [ ] 12.2 Create `src/tour_guide/cache/__init__.py` and `cache/poi_cache.py` with `POICache` implementing two-layer key scheme, TTL 30 days, LRU at 100 MB

## 13. POIService (Integration, TDD)

- [ ] 13.1 Write failing tests in `tests/integration/test_poi_service.py` covering: full pipeline returns enriched POIs with wiki and confidence, cache hit skips external clients; use fake clients and tmp_path cache
- [ ] 13.2 Create `services/poi_service.py` with `POIService.nearby(lat, lon, radius, persona, lang) -> list[POI]` combining OverpassClient + filter + WikipediaClient + ConfidenceClassifier + POICache

## 14. AppConfig

- [ ] 14.1 Write failing tests in `tests/unit/test_config.py` covering: config loads from env, missing GEMINI_API_KEY raises ValidationError, default values are correct
- [ ] 14.2 Create `src/tour_guide/config.py` with `AppConfig(BaseSettings)` for all environment variables

## 15. SSE Event Encoding

- [ ] 15.1 Write failing tests in `tests/unit/test_sse.py` for `encode_event()` format: `"event: {type}\ndata: {json}\n\n"`
- [ ] 15.2 Create `src/tour_guide/api/sse.py` with `encode_event(event_type: str, data: dict) -> str` helper

## 16. Health API Endpoint

- [ ] 16.1 Write failing tests in `tests/integration/test_health_api.py` verifying `GET /health` returns 200 with `{"status": "ok", "uptime_s": <non-negative>}`
- [ ] 16.2 Create `src/tour_guide/api/__init__.py` and `api/health.py` router with `GET /health` handler

## 17. POI Nearby API Endpoint

- [ ] 17.1 Write failing tests in `tests/integration/test_poi_api.py` covering: valid request returns 200 with pois list, invalid coordinates return 422, upstream 429 returns 429, upstream 503 returns 503; use fake POIService
- [ ] 17.2 Create `api/poi.py` router with `GET /poi/nearby` handler validating query params and calling POIService

## 18. Narration SSE API Endpoint

- [ ] 18.1 Write failing tests in `tests/integration/test_narration_api.py` covering: successful stream has correct event order (meta → text/audio → end), meta event has required fields, audio event has chunk_b64 and sentence_idx, error event on LLM rate limit, missing poi_id returns 422; use FakeLlmProvider and FakeTtsProvider
- [ ] 18.2 Create `api/narration.py` router with `POST /narration` SSE handler streaming NarrationService events via sse-starlette

## 19. Narration Cache (Filesystem, TDD)

- [ ] 19.1 Write failing tests in `tests/unit/test_narration_cache.py` covering: put then get returns same bytes, non-existent key returns None, LRU eviction at 500 MB; use `tmp_path`
- [ ] 19.2 Create `cache/narration_cache.py` with `NarrationCache` using key `{poi_id}|{persona}|{lang}|{length}`, storing audio bytes and transcript, LRU at 500 MB

## 20. Wire NarrationCache into NarrationService

- [ ] 20.1 Update `NarrationService` to accept `NarrationCache` and call `cache.get(key)` before pipeline; call `cache.put(key, audio, transcript)` after successful end event
- [ ] 20.2 Update narration service tests to verify cache is populated on miss and bypassed on hit

## 21. Real Provider Adapters

- [ ] 21.1 Create `providers/llm.py` `LiteLLMAdapter` implementing `LlmProvider` using `litellm.acompletion(stream=True)` for Gemini Flash model
- [ ] 21.2 Create `providers/tts.py` `GeminiTtsAdapter` implementing `TtsProvider` using `google-genai` SDK with configurable voice and speaking rate

## 22. FastAPI App Factory and DI Wiring

- [ ] 22.1 Create `src/tour_guide/main.py` with `create_app(config: AppConfig) -> FastAPI` factory that wires all dependencies (providers, services, clients, caches) via FastAPI lifespan or `Depends`, includes all routers
- [ ] 22.2 Wire real providers when `GEMINI_API_KEY` is set, fake providers in test mode
- [ ] 22.3 Verify app starts with all 3 routes registered (`/health`, `/poi/nearby`, `/narration`) via integration test

## 23. Full Test Suite and Linting

- [ ] 23.1 Run `pytest tests/unit/ tests/integration/ -v` and confirm all tests pass with 0 failures
- [ ] 23.2 Run `ruff check src/ tests/` and fix any lint errors until exit code 0
- [ ] 23.3 Run `ruff format --check src/ tests/` and fix formatting issues

## 24. Real-Provider Smoke Test

- [ ] 24.1 Create `tests/smoke/test_real_providers.py` with `@pytest.mark.real_provider` test running full narration pipeline against real Gemini API and asserting at least one `audio` event and one `end` event in SSE stream
- [ ] 24.2 Run smoke test manually with `pytest -m real_provider` and valid GEMINI_API_KEY to verify end-to-end pipeline

## 25. README Curl Recipes and Manual E2E Verification

- [ ] 25.1 Add curl recipe examples to `backend/README.md` for `GET /health`, `GET /poi/nearby` (with sample coords), and `POST /narration` (with sample poi_id, showing SSE stream output)
- [ ] 25.2 Run backend locally with `uvicorn tour_guide.main:app --reload` and manually execute all curl recipes to confirm expected output
