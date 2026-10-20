import math

from buddy_host.places.models import BBox

EARTH_RADIUS_M = 6_371_000.0
_M_PER_DEG_LAT = math.pi * EARTH_RADIUS_M / 180


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360


def angle_diff(a: float, b: float) -> float:
    diff = abs(a - b) % 360
    return 360 - diff if diff > 180 else diff


def bounding_box(lat: float, lon: float, radius_m: float) -> BBox:
    dlat = radius_m / _M_PER_DEG_LAT
    dlon = dlat / max(math.cos(math.radians(lat)), 1e-6)
    return BBox(lat - dlat, lon - dlon, lat + dlat, lon + dlon)
