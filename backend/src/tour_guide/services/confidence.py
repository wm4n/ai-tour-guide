from typing import Literal

from tour_guide.models.poi import Place, POIContext


class ConfidenceClassifier:
    """Classifier for POI confidence levels."""

    @staticmethod
    def classify(poi_context: POIContext) -> Literal["high", "medium", "low"]:
        """Classify confidence based on Wikipedia extract length."""
        if poi_context.wiki is None or not poi_context.wiki.extract:
            return "low"
        if len(poi_context.wiki.extract) >= 200:
            return "high"
        return "medium"

    @staticmethod
    def classify_place(place: Place) -> Literal["high", "medium", "low"]:
        """Classify confidence for a Google Places result.

        high   → rating >= 4.5 AND user_ratings_total >= 100
        medium → passes FoodieFilter but below high threshold
        low    → missing rating data
        """
        if place.rating is None or place.user_ratings_total is None:
            return "low"
        if place.rating >= 4.5 and place.user_ratings_total >= 100:
            return "high"
        return "medium"
