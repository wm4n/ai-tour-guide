# Capability: POI Map

## Purpose

Displays an interactive Google Maps view with POI markers, user location tracking, and confidence-based marker colour coding during an active tour session.

---

## Requirements

### Requirement: Fetch nearby POIs from backend
The app SHALL call `GET /poi/nearby` with current lat/lon/radius/persona and cache the result, refreshing when user moves more than 250m. The backend SHALL conditionally include foodie-specific fields (`rating`, `user_ratings_total`, `price_level`, `place_types`, `vicinity`) in the response only when `persona=foodie`; non-foodie responses SHALL NOT include these fields. `PoiNotifier.build()` SHALL listen to `effectivePositionStreamProvider` (instead of `positionStreamProvider`) so that POI fetches are triggered even when GPS is unavailable.

#### Scenario: Initial fetch on session start
- **WHEN** session becomes `active` and location is first available via `effectivePositionStreamProvider`
- **THEN** PoiProvider calls `/poi/nearby` and stores the returned `List<POI>`

#### Scenario: Initial fetch triggered by fallback position
- **WHEN** no GPS arrives within 5 seconds and `effectivePositionStreamProvider` emits a fallback position
- **THEN** PoiProvider calls `/poi/nearby` with the fallback coordinates

#### Scenario: Refresh after significant movement
- **WHEN** user moves more than 250m from the last fetch position
- **THEN** PoiProvider calls `/poi/nearby` again and updates the POI list

#### Scenario: Backend returns 429
- **WHEN** `/poi/nearby` returns HTTP 429
- **THEN** PoiProvider pauses polling and retries after the `Retry-After` header duration

#### Scenario: Foodie persona response includes rating fields
- **WHEN** `/poi/nearby?persona=foodie` returns a POI with rating data
- **THEN** the response JSON includes `rating`, `user_ratings_total`, `price_level`, `place_types`, `vicinity`

#### Scenario: Non-foodie persona response excludes rating fields
- **WHEN** `/poi/nearby?persona=history_uncle` returns a POI
- **THEN** the response JSON does NOT include `rating`, `user_ratings_total`, `place_types` keys

#### Scenario: BackendClient includes X-Api-Key on POI fetch
- **WHEN** PoiProvider calls `/poi/nearby` via `BackendClient`
- **THEN** the outgoing HTTP request includes the `X-Api-Key` header with the configured API key

---

### Requirement: Display POI markers on interactive map
The MapScreen SHALL display a full-screen Google Map with markers for each POI, colour-coded by confidence level.

#### Scenario: High confidence POI marker
- **WHEN** a POI has `confidence: "high"`
- **THEN** its marker is displayed in green

#### Scenario: Medium confidence POI marker
- **WHEN** a POI has `confidence: "medium"`
- **THEN** its marker is displayed in amber

#### Scenario: Low confidence POI marker
- **WHEN** a POI has `confidence: "low"`
- **THEN** its marker is displayed in red/grey

---

### Requirement: Manual narration trigger via map marker tap
The app SHALL allow users to manually trigger narration by tapping a POI marker on the map.

#### Scenario: User taps POI marker
- **WHEN** user taps a POI marker on the map
- **THEN** NarrationProvider.narrate(poi) is called immediately, bypassing TriggerEngine

---

### Requirement: User location tracking
The MapScreen SHALL show the user's current location as a blue dot and keep the map centred.

#### Scenario: Location updates
- **WHEN** GPS position updates arrive every 5 seconds
- **THEN** the blue dot moves to the new position on the map

#### Scenario: Low GPS accuracy
- **WHEN** GPS accuracy exceeds 100m
- **THEN** MapScreen displays a 「定位精度不足」 badge and TriggerEngine pauses evaluation

---

### Requirement: CountdownBadge UI
The app SHALL display a circular countdown badge in the bottom-right corner of the map screen when `TriggerState.isCountingDown` is true. The badge SHALL be hidden during narration and when no countdown is active. The `CircularProgressIndicator` inside the badge SHALL be wrapped in `SizedBox.expand()` so it fills the full badge container (72×72 logical pixels), preventing the indicator from overlapping the centered countdown text.

#### Scenario: Badge visible during countdown
- **WHEN** `TriggerState.isCountingDown` is true
- **THEN** `CountdownBadge` widget is visible with a `CircularProgressIndicator` and remaining seconds text

#### Scenario: Badge hidden when not counting down
- **WHEN** `TriggerState.isCountingDown` is false
- **THEN** `CountdownBadge` renders as `SizedBox.shrink()` (zero size)

#### Scenario: Badge tap skips countdown
- **WHEN** user taps the `CountdownBadge`
- **THEN** `TriggerNotifier.skipCountdown()` is called

#### Scenario: CircularProgressIndicator fills container via SizedBox.expand
- **WHEN** `CountdownBadge` is rendered with `isCountingDown == true`
- **THEN** the `CircularProgressIndicator` is a direct child of a `SizedBox` with `width == null` and `height == null` (i.e. `SizedBox.expand()`), ensuring the ring fills the container and does not overlap the text column

---

### Requirement: POI model supports nullable foodie fields
The `POI` dataclass (backend) and `POI` class (Flutter) SHALL include nullable foodie-specific fields: `rating: float | None`, `user_ratings_total: int | None`, `price_level: int | None`, `place_types: list[str] | None`, `vicinity: str | None`. These fields SHALL default to `None` for non-foodie POIs.

#### Scenario: Foodie POI parses all rating fields
- **WHEN** `POI.fromJson(json)` is called with a JSON containing `rating`, `user_ratings_total`, `price_level`, `place_types`, `vicinity`
- **THEN** all fields are correctly populated on the resulting POI

#### Scenario: Non-foodie POI has null foodie fields
- **WHEN** `POI.fromJson(json)` is called with a JSON without foodie fields
- **THEN** `poi.rating`, `poi.userRatingsTotal`, `poi.priceLevel`, `poi.placeTypes`, `poi.vicinity` are all `null`

---

### Requirement: POIService routes foodie persona to Google Places
The backend `POIService.nearby()` SHALL route requests with `persona == "foodie"` to `GooglePlacesClient.nearby_restaurants()` followed by `FoodieFilter.filter_places()`, and all other personas to the existing Overpass + Wikipedia pipeline. The foodie path SHALL NOT call Overpass.

#### Scenario: Foodie persona calls Google Places
- **WHEN** `POIService.nearby(lat, lon, radius, "foodie", lang)` is called
- **THEN** `GooglePlacesClient.nearby_restaurants()` is called and `OverpassClient.query()` is NOT called

#### Scenario: Non-foodie persona calls Overpass
- **WHEN** `POIService.nearby(lat, lon, radius, "history_uncle", lang)` is called
- **THEN** `OverpassClient.query()` is called and the result POIs have `rating == None`

#### Scenario: Foodie POI has no wiki
- **WHEN** `POIService` converts a `Place` to a `POI` for foodie persona
- **THEN** the resulting `POI.wiki == None` and `POI.place_types` matches `place.types`

#### Scenario: Foodie cache uses separate cache key
- **WHEN** a foodie `/poi/nearby` call is cached
- **THEN** the cache key starts with `region:foodie:` to avoid collision with non-foodie cache entries

---

### Requirement: POIService falls back to Wikipedia Geosearch when Overpass is unavailable
When `OverpassClient.query()` raises any exception (timeout, HTTP error, rate limit), `POIService` SHALL transparently fall back to `WikipediaClient.geosearch()` to return nearby Wikipedia articles as POIs. The fallback SHALL be invisible to callers — the same `list[POI]` shape is returned. Fallback nodes SHALL be tagged with `tourism=attraction` and `wikipedia=<lang>:<title>` so they pass `filter_poi_nodes` and flow through the existing confidence and narration pipeline unchanged.

#### Scenario: Overpass failure triggers Wikipedia Geosearch fallback
- **WHEN** `OverpassClient.query()` raises any exception after exhausting retries
- **THEN** `WikipediaClient.geosearch(lat, lon, radius, lang)` is called and its result is used instead of Overpass nodes

#### Scenario: Fallback nodes pass the POI filter
- **WHEN** Wikipedia Geosearch returns nodes tagged `{"tourism": "attraction", "wikipedia": "<lang>:<title>"}`
- **THEN** `filter_poi_nodes()` accepts all of them since they satisfy both the `tourism` and `wikipedia` tag requirements

#### Scenario: Fallback is logged
- **WHEN** Overpass fails and Wikipedia Geosearch fallback is activated
- **THEN** an `UPSTREAM_FAIL` log event with `service="overpass"` and `error=<exception type>` is emitted before the fallback call

#### Scenario: Wikipedia Geosearch requires User-Agent
- **WHEN** `WikipediaClient.geosearch()` calls the Wikipedia Action API (`/w/api.php`)
- **THEN** the HTTP client sends a `User-Agent` header in the format `ai-tour-guide/<version> (<url-or-email>)` to comply with Wikimedia bot policy
