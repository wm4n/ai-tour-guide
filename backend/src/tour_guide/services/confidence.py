from typing import Literal

from tour_guide.models.poi import POIContext


class ConfidenceClassifier:
    """Pure function classifier for POI confidence levels based on Wikipedia content."""

    @staticmethod
    def classify(poi_context: POIContext) -> Literal["high", "medium", "low"]:
        """
        Classify confidence level based on Wikipedia extract length.

        Args:
            poi_context: POI context containing OSM node and optional Wikipedia article

        Returns:
            "high" if wiki extract >= 200 chars
            "medium" if wiki extract between 1-199 chars
            "low" if wiki is None or extract is empty
        """
        if poi_context.wiki is None or not poi_context.wiki.extract:
            return "low"
        if len(poi_context.wiki.extract) >= 200:
            return "high"
        return "medium"
