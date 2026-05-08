## ADDED Requirements

### Requirement: Backend project skeleton
The system SHALL provide a Python 3.12 FastAPI backend project at `backend/` using PEP 621 `pyproject.toml` with src layout (`src/tour_guide/`), including all required dependencies (`fastapi`, `uvicorn`, `sse-starlette`, `pydantic-settings`, `httpx`, `litellm`, `google-genai`, `PyYAML`, `aiofiles`) and dev dependencies (`pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `respx`, `freezegun`).

#### Scenario: Project installs cleanly
- **WHEN** developer runs `pip install -e ".[dev]"` in `backend/`
- **THEN** all dependencies install without error and `pytest --version` prints successfully

#### Scenario: Linter passes on clean project
- **WHEN** developer runs `ruff check src/ tests/`
- **THEN** ruff exits with code 0 and no errors

---

### Requirement: AppConfig via environment variables
The system SHALL provide a `AppConfig` class using `pydantic-settings` that reads configuration from environment variables, including `GEMINI_API_KEY`, `HOST`, `PORT`, `POI_CACHE_DIR`, `NARRATION_CACHE_DIR`, `LOG_LEVEL`.

#### Scenario: Config loads from environment
- **WHEN** `GEMINI_API_KEY=test-key` is set in environment and `AppConfig()` is instantiated
- **THEN** `config.gemini_api_key == "test-key"` and all other fields use defaults

#### Scenario: Missing required API key raises error
- **WHEN** `GEMINI_API_KEY` is not set and `AppConfig()` is instantiated
- **THEN** a `ValidationError` is raised listing the missing field

---

### Requirement: Health endpoint
The system SHALL expose `GET /health` returning `{"status": "ok", "uptime_s": <seconds>}` with HTTP 200.

#### Scenario: Health check returns ok
- **WHEN** client sends `GET /health`
- **THEN** response is HTTP 200 with `{"status": "ok", "uptime_s": <non-negative integer>}`

---

### Requirement: POI query service
The system SHALL expose `GET /poi/nearby?lat=<float>&lon=<float>&radius=<int>&lang=<str>&persona=<str>` that returns a list of nearby points of interest by querying Overpass API (OSM) and enriching with Wikipedia summaries.

#### Scenario: Returns filtered POI list for non-foodie persona
- **WHEN** client sends `GET /poi/nearby?lat=25.1023&lon=121.5482&radius=500&lang=zh-TW&persona=history_uncle`
- **THEN** response is HTTP 200 with `{"pois": [...], "queried_at": "<ISO8601>"}` where each POI has `id`, `name`, `lat`, `lon`, `tags`, `wiki`, `distance_m`, `confidence`

#### Scenario: Invalid coordinates return 400
- **WHEN** client sends `GET /poi/nearby?lat=999&lon=121.5&radius=500&lang=zh-TW&persona=history_uncle`
- **THEN** response is HTTP 400 with error detail

#### Scenario: Upstream rate limit returns 429 with Retry-After
- **WHEN** Overpass API returns 429
- **THEN** `/poi/nearby` returns HTTP 429 with `Retry-After` header

#### Scenario: Upstream unavailable returns 503
- **WHEN** Overpass API returns 503
- **THEN** `/poi/nearby` returns HTTP 503

---

### Requirement: POI filtering rules
The system SHALL filter OSM nodes for non-foodie personas using a tourism/historic tag whitelist AND require the presence of a `wikipedia` or `wikidata` tag.

#### Scenario: Node with tourism tag and wiki tag passes filter
- **WHEN** OSM node has `tags: {"tourism": "museum", "wikipedia": "zh:故宮"}` 
- **THEN** the node passes the POI filter and is included in results

#### Scenario: Node without wiki tag is excluded
- **WHEN** OSM node has `tags: {"tourism": "museum"}` but no `wikipedia` or `wikidata` tag
- **THEN** the node is excluded from results

#### Scenario: Node with excluded tag type is excluded
- **WHEN** OSM node has `tags: {"shop": "convenience"}` (7-11 / gas station type)
- **THEN** the node is excluded regardless of other tags

---

### Requirement: Confidence classification
The system SHALL classify each POI's confidence level as `high`, `medium`, or `low` based on Wikipedia content richness.

#### Scenario: High confidence for full Wikipedia article
- **WHEN** POI has a Wikipedia article with intro section >= 200 characters
- **THEN** `ConfidenceClassifier.classify(poi_context)` returns `"high"`

#### Scenario: Medium confidence for short Wikipedia article
- **WHEN** POI has a Wikipedia article with intro section < 200 characters but > 0
- **THEN** `ConfidenceClassifier.classify(poi_context)` returns `"medium"`

#### Scenario: Low confidence for no Wikipedia content
- **WHEN** POI has only OSM tags and no Wikipedia content
- **THEN** `ConfidenceClassifier.classify(poi_context)` returns `"low"`

---

### Requirement: POI cache (filesystem, two-layer)
The system SHALL cache POI query results at two levels: region-level (lat/lon grid ~100m, `geo:{lat_3dp}:{lon_3dp}:{lang}`) and POI-level (`poi:{poi_id}:{lang}`), both with TTL of 30 days and LRU eviction at 100 MB total.

#### Scenario: Cache hit returns stored result
- **WHEN** a POI query key exists in cache and TTL has not expired
- **THEN** `POICache.get(key)` returns the cached value without calling Overpass

#### Scenario: Cache miss returns None
- **WHEN** a POI query key does not exist in cache
- **THEN** `POICache.get(key)` returns `None`

#### Scenario: Expired entry is treated as miss
- **WHEN** a cache entry was written 31 days ago (TTL 30 days)
- **THEN** `POICache.get(key)` returns `None` and the entry is eligible for eviction

---

### Requirement: SentenceSplitter pure function
The system SHALL provide a `SentenceSplitter` module with two functions:
- `split_complete_text(text: str) -> list[str]` — splits a complete text into sentences
- `StreamingSentenceBuffer` — accumulates streaming text chunks and yields complete sentences

Both SHALL handle Chinese and English punctuation: `。`, `！`, `？`, `.`, `!`, `?`.

#### Scenario: Chinese text splits on Chinese punctuation
- **WHEN** `split_complete_text("故宮博物院位於台北市。始建於1925年。")` is called
- **THEN** returns `["故宮博物院位於台北市。", "始建於1925年。"]`

#### Scenario: Mixed Chinese-English text splits correctly
- **WHEN** text contains both `。` and `.` delimiters
- **THEN** each sentence ends at its respective punctuation mark

#### Scenario: StreamingSentenceBuffer yields sentences as chunks arrive
- **WHEN** text is fed chunk by chunk to `StreamingSentenceBuffer.feed(chunk)`
- **THEN** complete sentences are yielded immediately upon punctuation detection, incomplete sentence is buffered

#### Scenario: StreamingSentenceBuffer.flush yields remaining buffer
- **WHEN** `flush()` is called after all chunks are fed
- **THEN** any remaining text in the buffer is yielded as a final sentence

---

### Requirement: Persona YAML loader
The system SHALL load persona definitions from YAML files at `prompts/personas/{id}.yaml` into a `PersonaConfig` dataclass. The YAML schema SHALL include: `id`, `display_name`, `voice`, `voice_style`, `style_profile`, `poi_source`, `system_prompt`, `narration_template`, `qa_template`, `system_messages`, `confidence_labels`.

#### Scenario: Valid YAML loads into PersonaConfig
- **WHEN** `PersonaLoader.load("history_uncle")` is called with a valid YAML file
- **THEN** returns a `PersonaConfig` with all fields populated

#### Scenario: Missing YAML file raises FileNotFoundError
- **WHEN** `PersonaLoader.load("nonexistent_persona")` is called
- **THEN** raises `FileNotFoundError`

#### Scenario: Invalid YAML schema raises ValidationError
- **WHEN** YAML is missing required field `id`
- **THEN** raises a validation error

---

### Requirement: Persona YAML schema for history_uncle
The system SHALL provide `prompts/personas/history_uncle.yaml` conforming to the persona YAML schema with the following fields:

```yaml
id: history_uncle
display_name:
  zh-TW: 歷史大叔
  en: The History Uncle
voice:
  zh-TW: Charon
  en: Charon
voice_style:
  speaking_rate: 0.95
  emotion: contemplative
style_profile:
  embellishment: 0.1
  preferred_topics: [history, cultural_context]
poi_source: osm_wikipedia
system_prompt: { zh-TW: "...", en: "..." }
narration_template: { zh-TW: "...", en: "..." }
qa_template: { zh-TW: "...", en: "..." }
system_messages: { zh-TW: { network_offline: [...], rate_limit: [...], ... } }
confidence_labels: { zh-TW: { high: null, medium: [...], low: [...] } }
```

#### Scenario: history_uncle persona loads successfully
- **WHEN** `PersonaLoader.load("history_uncle")` is called
- **THEN** `persona.id == "history_uncle"` and `persona.voice["zh-TW"] == "Charon"` and `persona.style_profile.embellishment == 0.1`

---

### Requirement: PromptBuilder pure function
The system SHALL provide `PromptBuilder.build(persona: PersonaConfig, poi: POIContext, lang: str, length: str) -> list[Message]` that assembles the LLM prompt using the persona's `narration_template`, inserting `poi_name`, `poi_context`, `target_length`.

#### Scenario: Build returns messages with system and user roles
- **WHEN** `PromptBuilder.build(history_uncle, poi_context, "zh-TW", "medium")` is called
- **THEN** returns a list with at least one `{"role": "system", "content": "..."}` and one `{"role": "user", "content": "..."}` message

#### Scenario: POI name appears in built prompt
- **WHEN** `poi_context.name == "國立故宮博物院"`
- **THEN** the built user message contains "國立故宮博物院"

#### Scenario: Wikipedia content is included when available
- **WHEN** `poi_context.wiki.extract` is non-empty
- **THEN** the built prompt includes wiki content (within first 1500 characters)

#### Scenario: Long Wikipedia extract is truncated
- **WHEN** `poi_context.wiki.extract` exceeds 1500 characters
- **THEN** the built prompt contains at most 1500 characters of wiki content

---

### Requirement: LlmProvider interface and LiteLLM adapter
The system SHALL define a `LlmProvider` Protocol with `async def chat_stream(self, messages: list[Message], opts: LlmOpts) -> AsyncIterator[str]` and provide a `LiteLLMAdapter` implementation using `litellm.acompletion` with `stream=True`.

#### Scenario: LiteLLMAdapter streams text chunks
- **WHEN** `LiteLLMAdapter.chat_stream(messages, opts)` is called with valid Gemini model
- **THEN** yields string chunks as they arrive from LiteLLM

#### Scenario: FakeLlmProvider yields scripted chunks
- **WHEN** `FakeLlmProvider(["Hello", " world"]).chat_stream(messages, opts)` is called
- **THEN** yields "Hello" then " world" in order

---

### Requirement: TtsProvider interface and Gemini adapter
The system SHALL define a `TtsProvider` Protocol with `async def synthesize(self, text: str, voice_id: str, opts: TtsOpts) -> AsyncIterator[bytes]` and provide a `GeminiTtsAdapter` implementation using `google-genai` SDK.

#### Scenario: GeminiTtsAdapter yields audio bytes
- **WHEN** `GeminiTtsAdapter.synthesize("故宮博物院", "Charon", opts)` is called
- **THEN** yields one or more `bytes` chunks

#### Scenario: FakeTtsProvider returns silent audio bytes
- **WHEN** `FakeTtsProvider().synthesize(any_text, any_voice, opts)` is called
- **THEN** yields a fixed non-empty `bytes` chunk (silent mp3 or similar)

---

### Requirement: NarrationService orchestration
The system SHALL provide `NarrationService.narrate(poi: POIContext, persona: PersonaConfig, lang: str, length: str, force_regenerate: bool) -> AsyncIterator[NarrationEvent]` that orchestrates: NarrationCache lookup → PromptBuilder → LlmProvider.chat_stream → SentenceSplitter → TtsProvider.synthesize → yield SSE events.

#### Scenario: Cache hit yields meta with cache_hit=true then audio events
- **WHEN** NarrationCache has a stored entry for the given key and `force_regenerate=False`
- **THEN** first event is `meta` with `cache_hit=true`, followed by `audio` events, then `end`

#### Scenario: Cache miss runs full pipeline and yields interleaved text and audio
- **WHEN** NarrationCache has no entry for the key
- **THEN** yields `meta` (cache_hit=false), then interleaved `text` and `audio` events per sentence, then `end`

#### Scenario: Completed narration is saved to NarrationCache
- **WHEN** full pipeline runs to completion without error
- **THEN** `NarrationCache.put(key, audio_bytes, transcript)` is called after `end` event

#### Scenario: force_regenerate bypasses cache
- **WHEN** NarrationCache has a stored entry but `force_regenerate=True`
- **THEN** cache is bypassed and full LLM+TTS pipeline runs

---

### Requirement: Narration SSE endpoint
The system SHALL expose `POST /narration` accepting `{"poi_id", "persona", "lang", "length", "force_regenerate"}` and streaming SSE events: `meta`, `text`, `audio` (interleaved), `end`, or `error`.

#### Scenario: Successful narration streams events in correct order
- **WHEN** `POST /narration {"poi_id": "osm:way:12345", "persona": "history_uncle", "lang": "zh-TW", "length": "medium", "force_regenerate": false}` with `Accept: text/event-stream`
- **THEN** response is HTTP 200, `Content-Type: text/event-stream`, first event is `meta`, last event is `end`, `text` and `audio` events appear between them

#### Scenario: meta event includes confidence and cache_hit fields
- **WHEN** narration starts
- **THEN** `meta` event data contains `{"poi_id": "...", "cache_hit": <bool>, "confidence": "<high|medium|low>", "estimated_duration_s": <int>}`

#### Scenario: audio event contains base64-encoded audio and sentence_idx
- **WHEN** TTS synthesizes a sentence
- **THEN** `audio` event data contains `{"chunk_b64": "<base64>", "sentence_idx": <int>}`

#### Scenario: error event on LLM rate limit
- **WHEN** LlmProvider raises a rate limit error
- **THEN** SSE stream emits `error` event with `{"code": "llm_rate_limit", "message": "...", "retry_after_s": <int>}`

#### Scenario: Missing poi_id returns 422
- **WHEN** `POST /narration` body is missing `poi_id`
- **THEN** response is HTTP 422 with validation error detail

---

### Requirement: NarrationCache (filesystem)
The system SHALL cache completed narration audio keyed by `{poi_id}|{persona}|{lang}|{length}` at `NARRATION_CACHE_DIR` (default `/tmp/tour_guide_narration_cache/`), with LRU eviction at 500 MB total.

#### Scenario: Cache put then get returns same audio bytes
- **WHEN** `NarrationCache.put(key, audio_bytes, transcript)` then `NarrationCache.get(key)`
- **THEN** returns the same `audio_bytes` and `transcript`

#### Scenario: Non-existent key returns None
- **WHEN** `NarrationCache.get("nonexistent-key")` is called
- **THEN** returns `None`

#### Scenario: Cache evicts oldest entries when over size limit
- **WHEN** total cached audio exceeds 500 MB
- **THEN** least recently accessed entries are deleted to bring total under limit

---

### Requirement: OverpassClient
The system SHALL provide `OverpassClient.query(bbox: BBox, tags: list[TagFilter]) -> list[OsmNode]` using httpx async client with retry (3 attempts, exponential backoff 1s/2s/4s) and rate limit handling.

#### Scenario: Successful query returns OsmNode list
- **WHEN** Overpass returns valid JSON response
- **THEN** `query()` returns list of `OsmNode` with `id`, `lat`, `lon`, `tags`

#### Scenario: Retry on transient 503
- **WHEN** Overpass returns 503 then 200 on second attempt
- **THEN** `query()` retries and returns result from second attempt

#### Scenario: Rate limit 429 raises OverpassRateLimitError
- **WHEN** Overpass returns 429
- **THEN** raises `OverpassRateLimitError` with `retry_after_s` attribute

---

### Requirement: WikipediaClient
The system SHALL provide `WikipediaClient.summary(title: str, lang: str) -> WikiArticle | None` that fetches the Wikipedia summary for a given title and language using the Wikipedia REST API.

#### Scenario: Known title returns WikiArticle with extract
- **WHEN** `WikipediaClient.summary("故宮博物院", "zh")` is called against Wikipedia API
- **THEN** returns `WikiArticle` with non-empty `extract` and `url`

#### Scenario: Unknown title returns None
- **WHEN** Wikipedia returns 404 for the title
- **THEN** `summary()` returns `None`

#### Scenario: Disambiguation page returns None
- **WHEN** Wikipedia article has `type: "disambiguation"`
- **THEN** `summary()` returns `None`

---

### Requirement: POIService.nearby combining Overpass and Wikipedia
The system SHALL provide `POIService.nearby(lat: float, lon: float, radius: int, persona: str, lang: str) -> list[POI]` that: queries OverpassClient → applies filter → looks up WikipediaClient for each POI → runs ConfidenceClassifier → applies POICache → returns sorted POI list.

#### Scenario: Full pipeline returns enriched POIs
- **WHEN** `POIService.nearby(25.1023, 121.5482, 500, "history_uncle", "zh-TW")` is called with fake Overpass and Wikipedia clients
- **THEN** returns list of POIs each with `wiki` field populated and `confidence` set

#### Scenario: Cache hit skips external client calls
- **WHEN** POICache has a valid entry for the region key
- **THEN** OverpassClient is not called

---

### Requirement: SSE event encoding helpers
The system SHALL provide `sse.py` with helper functions to encode SSE events as `"event: {type}\ndata: {json}\n\n"` strings, covering all event types: `meta`, `text`, `audio`, `end`, `error`, `transcript`.

#### Scenario: encode_event formats correctly
- **WHEN** `encode_event("text", {"chunk": "hello"})` is called
- **THEN** returns `"event: text\ndata: {\"chunk\": \"hello\"}\n\n"`

---

### Requirement: FastAPI app factory with dependency injection
The system SHALL provide `main.py` with a FastAPI app factory that wires all dependencies via DI (providers, services, clients, caches) using FastAPI `Depends` or lifespan context, reads config from `AppConfig`, and includes all routers.

#### Scenario: App starts with all routes registered
- **WHEN** FastAPI app is created via `create_app(config)`
- **THEN** routes `/health`, `/poi/nearby`, `/narration` are all registered

#### Scenario: App injects real providers when GEMINI_API_KEY is set
- **WHEN** `GEMINI_API_KEY` env var is present and app is started
- **THEN** `LiteLLMAdapter` and `GeminiTtsAdapter` are injected into `NarrationService`

---

### Requirement: Unit and integration test suite
The system SHALL provide unit tests for all pure-function modules and integration tests for all API endpoints using fake providers, achieving complete offline test execution.

#### Scenario: All unit tests pass without network access
- **WHEN** `pytest tests/unit/` is run in a network-isolated environment
- **THEN** all tests pass with 0 failures

#### Scenario: All integration tests pass without network access
- **WHEN** `pytest tests/integration/` is run using fake providers and respx HTTP mocks
- **THEN** all tests pass with 0 failures

#### Scenario: Smoke tests are gated behind real_provider marker
- **WHEN** `pytest` is run without `-m real_provider`
- **THEN** smoke tests in `tests/smoke/` are skipped

---

### Requirement: Real-provider smoke test
The system SHALL provide `tests/smoke/test_real_providers.py` marked `@pytest.mark.real_provider` that runs the full narration pipeline against real Gemini API to detect provider API changes.

#### Scenario: Smoke test runs full narration with real Gemini
- **WHEN** `pytest -m real_provider` is run with valid `GEMINI_API_KEY`
- **THEN** `/narration` SSE stream produces at least one `audio` event and one `end` event

---

### Requirement: README with setup, run, and curl recipes
The system SHALL provide `backend/README.md` with step-by-step setup instructions, run command, test command, and curl example recipes for all three endpoints.

#### Scenario: Developer can set up from scratch using README
- **WHEN** developer follows README steps on a clean Python 3.12 environment
- **THEN** backend starts and all curl examples in README return expected responses
