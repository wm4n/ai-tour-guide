## REMOVED Requirements

### Requirement: Display POI markers on interactive map
**Reason**: The product direction is auto-trigger only. Rendering coloured POI markers creates a dual trigger model (tap + auto-proximity) that is inconsistent with the intended UX. Markers also frequently show wrong positions due to the previously strict OSM filter.
**Migration**: No migration needed. The POI data continues to drive auto-trigger narration via `TriggerEngine`. The map displays only the user's real-time location dot (built-in `myLocationEnabled: true`). No user-facing setting or API endpoint is affected.

---

### Requirement: Manual narration trigger via map marker tap
**Reason**: Tap-to-narrate is removed together with map markers. The sole narration trigger is proximity-based auto-trigger via `TriggerEngine`. Removing this simplifies the trigger model to a single code path.
**Migration**: No migration needed. Auto-trigger continues unchanged via `trigger_provider.dart` and `TriggerEngine`. Users who previously relied on tap-trigger will be served by the improved auto-trigger coverage enabled by the relaxed OSM filter and Wikipedia fallback chain.

---

## MODIFIED Requirements

### Requirement: POIService falls back to Wikipedia Geosearch when Overpass is unavailable
When `OverpassClient.query()` raises any exception (timeout, HTTP error, rate limit), `POIService` SHALL transparently fall back to `WikipediaClient.geosearch()` to return nearby Wikipedia articles as POIs. The fallback SHALL be invisible to callers — the same `list[POI]` shape is returned. Fallback nodes SHALL be tagged with `tourism=attraction` and a non-empty `name` tag so they pass the relaxed `filter_poi_nodes` check (which now requires `name` instead of `wikipedia`/`wikidata`).

#### Scenario: Overpass failure triggers Wikipedia Geosearch fallback
- **WHEN** `OverpassClient.query()` raises any exception after exhausting retries
- **THEN** `WikipediaClient.geosearch(lat, lon, radius, lang)` is called and its result is used instead of Overpass nodes

#### Scenario: Fallback nodes pass the relaxed POI filter
- **WHEN** Wikipedia Geosearch returns nodes tagged `{"tourism": "attraction", "name": "<title>"}`
- **THEN** `filter_poi_nodes()` accepts all of them since they satisfy both the `tourism` and `name` tag requirements

#### Scenario: Fallback is logged
- **WHEN** Overpass fails and Wikipedia Geosearch fallback is activated
- **THEN** an `UPSTREAM_FAIL` log event with `service="overpass"` and `error=<exception type>` is emitted before the fallback call

#### Scenario: Wikipedia Geosearch requires User-Agent
- **WHEN** `WikipediaClient.geosearch()` calls the Wikipedia Action API (`/w/api.php`)
- **THEN** the HTTP client sends a `User-Agent` header in the format `ai-tour-guide/<version> (<url-or-email>)` to comply with Wikimedia bot policy

---

### Requirement: POIService routes foodie persona to Google Places
The backend `POIService.nearby()` SHALL route requests with `persona == "foodie"` to `GooglePlacesClient.nearby_restaurants()` followed by `FoodieFilter.filter_places()`, and all other personas to the Overpass + Wikipedia pipeline with `WikipediaResolver` fallback. The foodie path SHALL NOT call Overpass or `WikipediaResolver`.

#### Scenario: Foodie persona calls Google Places
- **WHEN** `POIService.nearby(lat, lon, radius, "foodie", lang)` is called
- **THEN** `GooglePlacesClient.nearby_restaurants()` is called and `OverpassClient.query()` is NOT called

#### Scenario: Non-foodie persona calls Overpass with resolver fallback
- **WHEN** `POIService.nearby(lat, lon, radius, "history_uncle", lang)` is called
- **THEN** `OverpassClient.query()` is called, filtered nodes are sorted by distance and limited to the nearest 20, and `WikipediaResolver.resolve()` is called for any node that lacks an OSM `wikipedia` tag

#### Scenario: Foodie POI has no wiki
- **WHEN** `POIService` converts a `Place` to a `POI` for foodie persona
- **THEN** the resulting `POI.wiki == None` and `POI.place_types` matches `place.types`

#### Scenario: Foodie cache uses separate cache key
- **WHEN** a foodie `/poi/nearby` call is cached
- **THEN** the cache key starts with `region:foodie:` to avoid collision with non-foodie cache entries

---

## ADDED Requirements

### Requirement: OSM POI filter requires name tag instead of wikidata tag
`filter_poi_nodes()` SHALL keep an OSM node if and only if:
- It has at least one tag from `{"tourism", "historic"}`, AND
- It has a non-empty `name` tag.

The previous requirement for a `wikipedia` or `wikidata` tag is removed. Wikipedia data is now fetched by name via `WikipediaResolver` rather than relying on the OSM annotation.

#### Scenario: Node with tourism and name but no wikidata passes
- **WHEN** `filter_poi_nodes([node])` is called with a node having `{"tourism": "museum", "name": "Local Museum"}`
- **THEN** the node is included in the result

#### Scenario: Node with tourism but no name is excluded
- **WHEN** `filter_poi_nodes([node])` is called with a node having `{"tourism": "museum"}` and no `name` tag
- **THEN** the node is excluded from the result

#### Scenario: Node with only shop tag is excluded
- **WHEN** `filter_poi_nodes([node])` is called with a node having `{"shop": "book", "name": "Bookstore"}` but no tourism/historic tag
- **THEN** the node is excluded from the result

---

### Requirement: POIService limits Wikipedia lookups to the 20 nearest nodes
After applying `filter_poi_nodes()`, `POIService._nearby_osm()` SHALL sort the filtered nodes by haversine distance from the request origin and process only the nearest 20 before performing any Wikipedia lookups.

#### Scenario: Dense area caps at 20 nodes
- **WHEN** `filter_poi_nodes()` returns 50 nodes and the request origin is set
- **THEN** only the 20 closest nodes are sent through the Wikipedia lookup pipeline

#### Scenario: Sparse area uses all available nodes
- **WHEN** `filter_poi_nodes()` returns 8 nodes
- **THEN** all 8 nodes are sent through the Wikipedia lookup pipeline

---

### Requirement: POIService injects and uses WikipediaResolver
`POIService` SHALL accept an optional `resolver: WikipediaResolver | None` parameter in its constructor. When `resolver` is not `None`, `_nearby_osm()` SHALL call `resolver.resolve(poi_name, lat, lon, lang)` for any node where the OSM `wikipedia` tag yields no result from `WikipediaClient.summary()`.

#### Scenario: Resolver called when OSM wiki tag absent
- **WHEN** a filtered node has no `wikipedia` tag and `resolver` is set
- **THEN** `resolver.resolve(node.name, node.lat, node.lon, lang)` is called

#### Scenario: Resolver not called when OSM wiki tag present and returns article
- **WHEN** a filtered node has a `wikipedia` tag and `WikipediaClient.summary()` returns an article
- **THEN** `resolver.resolve()` is NOT called for that node

#### Scenario: Resolver returns None leaves wiki as None
- **WHEN** `resolver.resolve()` returns `None`
- **THEN** the resulting `POI.wiki` is `None` and the `no_data_context` fallback in `NarrationService` handles it
