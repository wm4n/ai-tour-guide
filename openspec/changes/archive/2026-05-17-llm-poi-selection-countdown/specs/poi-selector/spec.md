## ADDED Requirements

### Requirement: LLM-based POI selection from candidates
The backend `POISelectorService` SHALL accept a list of `POICandidate` objects and use a non-streaming LLM call to select the single most narratable POI, returning its `poi_id`. The selector SHALL prefer POIs with Wikipedia data, closer distance, and different theme from the previous narration.

#### Scenario: Selector returns a valid poi_id
- **WHEN** `POISelectorService.select()` is called with a non-empty candidates list
- **THEN** the returned `poi_id` MUST be one of the `poi_id` values in the candidates list

#### Scenario: Invalid LLM response falls back to first candidate
- **WHEN** the LLM returns a string that does not match any candidate's `poi_id`
- **THEN** `POISelectorService.select()` SHALL return `candidates[0].poi_id` and log a warning

#### Scenario: Previous selection context included in prompt
- **WHEN** `previous` parameter is a `PreviousSelection` with `poi_name` and `script`
- **THEN** the LLM prompt SHALL include the previous POI name and a script preview (up to 400 chars)

#### Scenario: Selection is logged with candidate count
- **WHEN** a POI is selected
- **THEN** a `POI_SELECTION` log event SHALL be emitted with `selected_id`, `candidate_count`, and `has_previous` fields

#### Scenario: Empty candidates raises error
- **WHEN** `POISelectorService.select()` is called with an empty list
- **THEN** `ValueError` SHALL be raised with message "candidates list is empty"

---

### Requirement: Multi-candidate narration request format
The `POST /narration` endpoint SHALL accept `candidates: list[POICandidate]` instead of a single POI context. Each `POICandidate` SHALL include `poi_id`, `poi_name`, `poi_lat`, `poi_lon`, `distance_m`, `poi_tags`, `wiki_title`, and `wiki_extract`.

#### Scenario: Endpoint validates non-empty candidates
- **WHEN** `POST /narration` is called with `candidates: []`
- **THEN** endpoint responds with HTTP 400 and detail "candidates list must not be empty"

#### Scenario: Endpoint processes valid candidates list
- **WHEN** `POST /narration` is called with a valid `candidates` list and known `persona`
- **THEN** `POISelectorService.select()` is called first, then narration streams for the selected POI

#### Scenario: Optional previous_selection forwarded to selector
- **WHEN** request includes `previous_selection` with `poi_id`, `poi_name`, and `script`
- **THEN** `POISelectorService.select()` receives the `previous` parameter populated

---

### Requirement: poi_name in backend MetaEvent
The backend `MetaEvent` dataclass SHALL include a `poi_name` field populated from the selected POI's `name` tag (or `poi_id` as fallback).

#### Scenario: MetaEvent carries poi_name on cache miss
- **WHEN** narration is generated fresh (cache miss)
- **THEN** MetaEvent SSE event includes `poi_name` matching the selected POI's name tag

#### Scenario: MetaEvent carries poi_name on cache hit
- **WHEN** narration is served from cache
- **THEN** MetaEvent SSE event includes `poi_name` (not empty)
