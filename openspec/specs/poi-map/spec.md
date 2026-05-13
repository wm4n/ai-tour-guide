# Capability: POI Map

## Purpose

Displays an interactive Google Maps view with POI markers, user location tracking, and confidence-based marker colour coding during an active tour session.

---

## Requirements

### Requirement: Fetch nearby POIs from backend
The app SHALL call `GET /poi/nearby` with current lat/lon/radius and cache the result, refreshing when user moves more than 250m.

#### Scenario: Initial fetch on session start
- **WHEN** session becomes `active` and location is first available
- **THEN** PoiProvider calls `/poi/nearby` and stores the returned `List<POI>`

#### Scenario: Refresh after significant movement
- **WHEN** user moves more than 250m from the last fetch position
- **THEN** PoiProvider calls `/poi/nearby` again and updates the POI list

#### Scenario: Backend returns 429
- **WHEN** `/poi/nearby` returns HTTP 429
- **THEN** PoiProvider pauses polling and retries after the `Retry-After` header duration

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
