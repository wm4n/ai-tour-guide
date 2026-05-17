## MODIFIED Requirements

### Requirement: LLM-based POI selection from candidates
The backend `POISelectorService` SHALL accept a list of `POICandidate` objects and use a non-streaming LLM call to select the single most narratable POI, returning its `poi_id`, OR return `None` if ALL candidates are trivial. The selector SHALL prefer POIs with Wikipedia data, closer distance, and different theme from the previous narration. When ALL candidates are trivial (infrastructure signage with no Wikipedia data), the selector SHALL return `None` (SKIP).

#### Scenario: Selector returns a valid poi_id
- **WHEN** `POISelectorService.select()` is called with a non-empty candidates list that includes at least one worth-narrating POI
- **THEN** the returned `poi_id` MUST be one of the `poi_id` values in the candidates list

#### Scenario: Selector returns None when all candidates are trivial
- **WHEN** `POISelectorService.select()` is called and the LLM responds with "SKIP"
- **THEN** `POISelectorService.select()` SHALL return `None`

#### Scenario: Invalid LLM response falls back to first candidate
- **WHEN** the LLM returns a string that does not match any candidate's `poi_id` AND is not the word "SKIP"
- **THEN** `POISelectorService.select()` SHALL return `candidates[0].poi_id` and log a warning

#### Scenario: Previous selection context included in prompt
- **WHEN** `previous` parameter is a `PreviousSelection` with `poi_name` and `script`
- **THEN** the LLM prompt SHALL include the previous POI name and a script preview (up to 400 chars)

#### Scenario: Selection is logged with candidate count
- **WHEN** a POI is selected (non-None result)
- **THEN** a `POI_SELECTION` log event SHALL be emitted with `selected_id`, `candidate_count`, and `has_previous` fields

#### Scenario: SKIP is logged with candidate count
- **WHEN** `POISelectorService.select()` returns `None`
- **THEN** a `POI_SELECTION_SKIP` log event SHALL be emitted with `candidate_count` and `has_previous` fields

#### Scenario: Empty candidates raises error
- **WHEN** `POISelectorService.select()` is called with an empty list
- **THEN** `ValueError` SHALL be raised with message "candidates list is empty"
