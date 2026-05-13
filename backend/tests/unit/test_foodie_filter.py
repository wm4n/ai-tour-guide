"""Unit tests for FoodieFilter pure function."""

import pytest

from tour_guide.models.poi import Place
from tour_guide.services.foodie_filter import filter_places


def _place(rating: float | None, count: int | None, *, name: str = "餐廳") -> Place:
    return Place(
        id=f"gplace:{name}",
        name=name,
        lat=25.0,
        lon=121.0,
        rating=rating,
        user_ratings_total=count,
        price_level=2,
        types=["restaurant"],
        vicinity="台北市",
    )


class TestFoodieFilterNormalHours:
    """Outside meal hours: rating >= 4.3 AND count >= 50."""

    def test_passes_when_above_threshold(self):
        place = _place(4.3, 50)
        assert filter_places([place], current_hour=10) == [place]

    def test_passes_high_rating(self):
        place = _place(4.8, 200)
        assert filter_places([place], current_hour=8) == [place]

    def test_excluded_rating_below_threshold(self):
        place = _place(4.2, 100)
        assert filter_places([place], current_hour=10) == []

    def test_excluded_count_below_threshold(self):
        place = _place(4.5, 49)
        assert filter_places([place], current_hour=9) == []

    def test_excluded_both_below(self):
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=16) == []


class TestFoodieFilterMealHours:
    """During meal hours (11-13 / 17-20): rating >= 4.0 AND count >= 30."""

    @pytest.mark.parametrize("hour", [11, 12, 13, 17, 18, 19, 20])
    def test_lower_threshold_applies_during_meal_hours(self, hour):
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=hour) == [place]

    def test_excluded_at_boundary_hour_10(self):
        """Hour 10 is NOT meal time — normal threshold applies."""
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=10) == []

    def test_excluded_at_boundary_hour_14(self):
        """Hour 14 is NOT meal time — normal threshold applies."""
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=14) == []

    def test_excluded_at_boundary_hour_21(self):
        """Hour 21 is NOT meal time — normal threshold applies."""
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=21) == []


class TestFoodieFilterNoneValues:
    def test_excluded_when_rating_none(self):
        place = _place(None, 100)
        assert filter_places([place], current_hour=12) == []

    def test_excluded_when_count_none(self):
        place = _place(4.5, None)
        assert filter_places([place], current_hour=12) == []

    def test_excluded_when_both_none(self):
        place = _place(None, None)
        assert filter_places([place], current_hour=12) == []


class TestFoodieFilterMixed:
    def test_mixed_list_returns_only_qualifying(self):
        good = _place(4.5, 100, name="好店")
        low_rating = _place(3.9, 200, name="低評")
        no_rating = _place(None, 50, name="無評")
        result = filter_places([good, low_rating, no_rating], current_hour=10)
        assert result == [good]

    def test_empty_list(self):
        assert filter_places([], current_hour=12) == []
