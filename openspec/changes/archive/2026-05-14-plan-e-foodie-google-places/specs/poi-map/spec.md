## MODIFIED Requirements

### Requirement: Fetch nearby POIs from backend
The app SHALL call `GET /poi/nearby` with current lat/lon/radius/persona and cache the result, refreshing when user moves more than 250m. The backend SHALL conditionally include foodie-specific fields (`rating`, `user_ratings_total`, `price_level`, `place_types`, `vicinity`) in the response only when `persona=foodie`; non-foodie responses SHALL NOT include these fields.

#### Scenario: Initial fetch on session start
- **WHEN** session becomes `active` and location is first available
- **THEN** PoiProvider calls `/poi/nearby` and stores the returned `List<POI>`

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

---

## ADDED Requirements

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
