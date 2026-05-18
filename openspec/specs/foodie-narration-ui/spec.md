# Capability: Foodie Narration UI

## Purpose

Displays foodie-specific information (rating, user rating count, price level) in the NarrationSheet widget when a foodie POI is being narrated.

---

## Requirements

### Requirement: NarrationSheet displays foodie rating bar
The `NarrationSheet` widget SHALL display a `_FoodieRatingBar` below the subtitle area when the current POI has a non-null `rating`. The bar SHALL show: star emoji, rating to 1 decimal place, user ratings count in parentheses, and price level as `$` symbols (1=$, 2=$$, 3=$$$, 4=$$$$).

#### Scenario: Foodie POI shows rating bar
- **WHEN** `NarrationState.currentPoi.rating` is non-null (e.g., 4.6)
- **THEN** NarrationSheet displays text containing "4.6", the user ratings count, and "$$" for priceLevel=2

#### Scenario: Non-foodie POI hides rating bar
- **WHEN** `NarrationState.currentPoi.rating` is null
- **THEN** NarrationSheet does NOT display any rating/star content (`_FoodieRatingBar` returns `SizedBox.shrink()`)

#### Scenario: Null price level omits dollar signs
- **WHEN** `NarrationState.currentPoi.priceLevel` is null
- **THEN** no `$` symbols are shown in the rating bar

---

### Requirement: _FoodieRatingBar is a private widget
The `_FoodieRatingBar` SHALL be implemented as a private `StatelessWidget` within `narration_sheet.dart`, accepting a `POI` parameter.

#### Scenario: Widget exists in narration_sheet.dart
- **WHEN** `narration_sheet.dart` is imported
- **THEN** `_FoodieRatingBar` is accessible within the same file and used by `NarrationSheet.build()`
