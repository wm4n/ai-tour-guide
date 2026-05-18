## MODIFIED Requirements

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
