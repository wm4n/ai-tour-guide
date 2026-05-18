## Context

The AI tour guide currently uses a strict OSM POI filter that requires both a `tourism`/`historic` tag AND a `wikipedia`/`wikidata` tag. In practice, most OSM nodes carry the tourism/historic category tag but lack a `wikidata` annotation, so a large fraction of real landmarks is silently dropped before the Wikipedia lookup step.

In addition, the Flutter map renders coloured POI markers that users can tap to trigger narration — creating a dual trigger model (tap + auto-proximity) that conflicts with the intended auto-only product direction.

Finally, the LLM narration prompts lack explicit opening-style instructions, allowing greetings ("哈囉各位！") instead of the desired scene-action sentence openings.

**Current state:**
- `poi_filter.py`: keeps nodes with `(tourism|historic) AND (wikipedia|wikidata)`
- `poi_service.py`: calls `wikipedia.summary(wiki_tag_title)` — no fallback if the tag is absent
- `map_screen.dart`: builds a markers `Set<Marker>` from `poiProvider` and renders them on `GoogleMap`
- Persona YAMLs: no `no_data_context` field; narration templates lack opening-style rules

**Stakeholders:** Mobile users navigating with auto-triggered narration; no API contract changes.

## Goals / Non-Goals

**Goals:**
- Increase the number of POIs that enter the pipeline by relaxing the OSM filter from wikidata-required to name-required
- Recover Wikipedia data for wikidata-free nodes via a multi-level name search fallback (poi_name → suburb → city)
- Remove POI map markers and tap-trigger to simplify the UX to auto-trigger only
- Ensure narration never opens with a greeting by adding per-persona opening instructions
- Provide a pre-written persona-specific verbal fallback when Wikipedia data cannot be found at any fallback level, skipping the LLM entirely

**Non-Goals:**
- Changing OSM tag categories beyond `tourism` and `historic`
- Foodie persona POI selection (uses Google Places, unchanged)
- Confidence scoring algorithm changes
- Background narration / notification flow changes
- Any breaking change to the narration HTTP API or Flutter↔backend event protocol

## Decisions

### Decision 1: Relax filter to require `name` tag instead of `wikidata` tag

**Chosen:** Keep node if it has `(tourism|historic) AND name`.

**Rationale:** The `name` tag is present on nearly every OSM node that is actually a named landmark, making it a reliable proxy for "worth narrating". Wikipedia data is then fetched by name via the new resolver rather than relying on OSM's `wikidata` annotation, which is sparsely populated.

**Alternative considered:** Keep `wikidata` requirement and improve OSM data quality externally — rejected because it is not under our control and would take years.

---

### Decision 2: Four-level Wikipedia fallback via `WikipediaResolver`

**Chosen:** Encapsulate the fallback chain in a dedicated `WikipediaResolver` service that calls `WikipediaClient.search()` (new opensearch method) and `NominatimClient.reverse()` for progressive context broadening.

Fallback order:
1. Search by `poi_name`
2. Search by `"poi_name，suburb"` (Nominatim reverse geocoding)
3. Search by `"poi_name，city"` (Nominatim reverse geocoding)
4. Return `None`

**Rationale:** A dedicated resolver keeps `POIService` clean and makes the fallback chain independently testable. Nominatim is called only once per node (not per fallback level) so the overhead is minimal.

**Alternative considered:** Embed all fallback logic directly in `POIService._nearby_osm()` — rejected because it entangles HTTP client management with business logic and makes unit testing harder.

---

### Decision 3: Limit Wikipedia lookups to the 20 nearest nodes

**Chosen:** After filtering, sort by haversine distance and slice to `[:20]` before any HTTP calls.

**Rationale:** Dense urban areas can yield hundreds of tourism nodes in a 500 m radius. Without a limit, the fallback chain (up to 4 HTTP calls per node: Nominatim + 3 Wikipedia searches) would create unacceptable latency. 20 nodes is well above the practical number a user would encounter during a walk.

**Alternative considered:** Dynamic limit based on API response time budget — rejected as over-engineering for the current scale.

---

### Decision 4: Pre-written `no_data_context` short-circuit in `NarrationService`

**Chosen:** Add a check `if poi.wiki is None` immediately after the MetaEvent yield and before the LLM prompt build. TTS the `persona.no_data_context[lang]` phrase directly and return.

**Rationale:** Calling the LLM with no Wikipedia context wastes ~1–2 s and produces generic or hallucinated output. A pre-written phrase is faster, more brand-consistent, and avoids LLM cost for empty-data nodes.

**Alternative considered:** Pass empty context to the LLM with a system instruction to say something brief — rejected because it still incurs LLM latency and is less predictable.

---

### Decision 5: `NominatimClient` uses the shared `httpx.AsyncClient`

**Chosen:** Accept an optional `httpx.AsyncClient` in the constructor (same pattern as `WikipediaClient` and `OverpassClient`). `main.py` passes the same shared client instance.

**Rationale:** Reusing the shared connection pool avoids opening extra TCP connections. Nominatim policy requires a descriptive `User-Agent` header — the shared client can be configured with this header at construction in `main.py`, or `NominatimClient` can add it per-request if the shared client is generic.

---

### Decision 6: Remove map markers — no migration needed

**Chosen:** Delete `poi_marker.dart` entirely and strip the markers-building block from `map_screen.dart`. No deprecation path is needed because tap-trigger is being removed, not replaced.

**Rationale:** There is no external API surface involved — markers are a purely UI concern. The POI data still exists; it just is not rendered. Auto-trigger continues through `trigger_provider.dart`, which is untouched.

## Risks / Trade-offs

- **[Risk] Nominatim rate-limiting** — Nominatim's free tier enforces 1 req/s. With 20 nodes × 1 Nominatim call each, a full refresh could take ≥ 20 s in the worst case (all nodes lacking OSM wiki tags). → **Mitigation**: The Nominatim call is skipped for any node where the direct name search succeeds (level 1). In practice only a subset of nodes will reach level 2+. Region-level caching in `POIService` ensures the hit happens at most once per geographic area per session.

- **[Risk] Opensearch returns wrong article** — Wikipedia opensearch can return a disambiguation page or an unrelated article for short/ambiguous names (e.g., "中山"). → **Mitigation**: The summary text is fed to the LLM together with the POI name; the LLM can self-correct if the article is obviously wrong. A future confidence-scoring improvement can filter low-relevance articles.

- **[Risk] Persona YAML narration_template changes affect existing narrations in cache** — If cached narrations were generated with the old template (no opening rule), the new rule only applies to newly generated narrations. → **Mitigation**: Acceptable — cache is session-scoped. No persistent cache invalidation is needed.

- **[Risk] Removing map markers changes perceived app responsiveness** — Users no longer see which POIs are loaded near them. → **Mitigation**: The narration sheet and auto-trigger provide feedback. A future "nearby POIs" list screen can be added if needed.
