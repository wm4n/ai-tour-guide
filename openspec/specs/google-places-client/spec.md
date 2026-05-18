# Capability: Google Places Client

## Purpose

Abstracts interaction with the Google Places API (New) for fetching nearby restaurants and providing dependency injection in tests through Protocol-based design.

---

## Requirements

### Requirement: GooglePlacesClient protocol abstraction
The backend SHALL define a `GooglePlacesClient` Protocol with a single `nearby_restaurants(lat, lon, radius_m) -> list[Place]` method, enabling dependency injection and offline testing.

#### Scenario: Protocol defines nearby_restaurants
- **WHEN** any class implements `GooglePlacesClient` Protocol
- **THEN** it SHALL provide `async def nearby_restaurants(self, lat: float, lon: float, radius_m: int) -> list[Place]`

---

### Requirement: FakeGooglePlacesClient for testing
The backend SHALL provide a `FakeGooglePlacesClient` that accepts `scripted_places: list[Place]` at construction and returns them unchanged without making network calls.

#### Scenario: Returns scripted places unchanged
- **WHEN** `FakeGooglePlacesClient(scripted_places=[place1, place2]).nearby_restaurants(...)` is called
- **THEN** it returns `[place1, place2]` without any HTTP request

#### Scenario: Empty scripted places returns empty list
- **WHEN** `FakeGooglePlacesClient(scripted_places=[]).nearby_restaurants(...)` is called
- **THEN** it returns `[]`

---

### Requirement: RealGooglePlacesClient calls Places API (New)
The backend SHALL provide a `RealGooglePlacesClient` that calls the Google Places API (New) Nearby Search endpoint with `includedTypes: ["restaurant", "cafe", "bakery"]` and parses the response into `list[Place]`.

#### Scenario: API call uses correct field mask
- **WHEN** `RealGooglePlacesClient.nearby_restaurants(lat, lon, radius_m)` is called
- **THEN** it sends POST to `https://places.googleapis.com/v1/places:searchNearby` with `X-Goog-FieldMask` header containing `places.id`, `places.displayName`, `places.location`, `places.rating`, `places.userRatingCount`, `places.priceLevel`, `places.types`, `places.formattedAddress`

#### Scenario: Exponential backoff on transient errors
- **WHEN** the API returns a transient error (non-429)
- **THEN** client retries with delays of 1s, 2s, 4s before raising

#### Scenario: Rate limit error raises immediately
- **WHEN** the API returns HTTP 429
- **THEN** client raises `GooglePlacesRateLimitError` without retry

---

### Requirement: AppConfig includes optional GOOGLE_PLACES_API_KEY
The backend `AppConfig` SHALL include a `google_places_api_key: str` field mapped to the `GOOGLE_PLACES_API_KEY` environment variable, defaulting to empty string.

#### Scenario: Config loads key from environment
- **WHEN** `GOOGLE_PLACES_API_KEY=abc123` is set in environment
- **THEN** `AppConfig().google_places_api_key == "abc123"`

#### Scenario: Config defaults to empty string
- **WHEN** `GOOGLE_PLACES_API_KEY` is not set
- **THEN** `AppConfig().google_places_api_key == ""`

---

### Requirement: main.py wires Real or Fake client based on config
The backend `create_app()` factory SHALL instantiate `RealGooglePlacesClient` when `config.google_places_api_key` is non-empty, and `FakeGooglePlacesClient(scripted_places=[])` otherwise.

#### Scenario: Non-empty API key uses Real client
- **WHEN** `GOOGLE_PLACES_API_KEY` is set to a non-empty value
- **THEN** `POIService` receives a `RealGooglePlacesClient` instance

#### Scenario: Empty API key uses Fake client
- **WHEN** `GOOGLE_PLACES_API_KEY` is empty or absent
- **THEN** `POIService` receives a `FakeGooglePlacesClient(scripted_places=[])` instance

---

### Requirement: Place dataclass for Google Places results
The backend SHALL define a `Place` dataclass with fields: `id` (prefixed `gplace:`), `name`, `lat`, `lon`, `rating: float | None`, `user_ratings_total: int | None`, `price_level: int | None`, `types: list[str]`, `vicinity: str`.

#### Scenario: Place stores nullable rating fields
- **WHEN** a Place is created with `rating=None` and `user_ratings_total=None`
- **THEN** `place.rating is None` and `place.user_ratings_total is None`

#### Scenario: Place id prefixed with gplace:
- **WHEN** a Place is parsed from Google Places API response with `id: "ChIJ123"`
- **THEN** `place.id == "gplace:ChIJ123"`

---

### Requirement: FoodieFilter pure function with meal-time threshold
The backend SHALL provide `filter_places(places: list[Place], current_hour: int) -> list[Place]` that filters by rating thresholds: meal hours (11–13, 17–20) use `rating ≥ 4.0` AND `user_ratings_total ≥ 30`; other hours use `rating ≥ 4.3` AND `user_ratings_total ≥ 50`. Places with `None` rating or count are excluded.

#### Scenario: Normal hours excludes low-rated place
- **WHEN** `filter_places([place(rating=4.2, count=100)], current_hour=10)` is called
- **THEN** returns `[]`

#### Scenario: Meal hours applies lower threshold
- **WHEN** `filter_places([place(rating=4.0, count=30)], current_hour=12)` is called
- **THEN** returns the place

#### Scenario: None rating excludes place at any hour
- **WHEN** a Place has `rating=None`
- **THEN** `filter_places([place], current_hour=12)` returns `[]`

#### Scenario: Meal hours boundary — hour 14 is not meal time
- **WHEN** `filter_places([place(rating=4.0, count=30)], current_hour=14)` is called
- **THEN** returns `[]` (normal threshold applies, 4.0 < 4.3)

---

### Requirement: ConfidenceClassifier.classify_place for Google Places
The backend `ConfidenceClassifier` SHALL provide a static `classify_place(place: Place) -> str` method: `"high"` if `rating ≥ 4.5 AND user_ratings_total ≥ 100`; `"medium"` if passes FoodieFilter but below high threshold; `"low"` if rating is None.

#### Scenario: High confidence for top-rated place
- **WHEN** `place.rating == 4.5` and `place.user_ratings_total == 100`
- **THEN** `ConfidenceClassifier.classify_place(place) == "high"`

#### Scenario: Medium confidence for borderline place
- **WHEN** `place.rating == 4.3` and `place.user_ratings_total == 200`
- **THEN** `ConfidenceClassifier.classify_place(place) == "medium"`

#### Scenario: Low confidence when rating missing
- **WHEN** `place.rating is None`
- **THEN** `ConfidenceClassifier.classify_place(place) == "low"`
