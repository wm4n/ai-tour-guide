"""Foodie filter: rating + meal-time threshold filtering for Google Places results."""

from tour_guide.models.poi import Place

_NORMAL_MIN_RATING = 4.3
_NORMAL_MIN_COUNT = 50

_MEAL_MIN_RATING = 4.0
_MEAL_MIN_COUNT = 30

_MEAL_HOURS = frozenset(range(11, 14)) | frozenset(range(17, 21))


def filter_places(places: list[Place], current_hour: int) -> list[Place]:
    """Filter restaurant places by rating threshold (meal-time aware).

    Args:
        places: List of Place objects from Google Places API.
        current_hour: Current hour (0-23), injected for testability.

    Returns:
        Filtered list keeping only places above threshold.
    """
    is_meal_time = current_hour in _MEAL_HOURS
    min_rating = _MEAL_MIN_RATING if is_meal_time else _NORMAL_MIN_RATING
    min_count = _MEAL_MIN_COUNT if is_meal_time else _NORMAL_MIN_COUNT

    return [
        p for p in places
        if p.rating is not None
        and p.user_ratings_total is not None
        and p.rating >= min_rating
        and p.user_ratings_total >= min_count
    ]
