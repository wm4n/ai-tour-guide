import pytest

from buddy_host.places.geo import angle_diff, bearing_deg, bounding_box, haversine_m


def test_one_degree_of_latitude_is_about_111_km():
    assert haversine_m(0, 0, 1, 0) == pytest.approx(111_195, abs=200)


def test_same_point_is_zero():
    assert haversine_m(25.05, 121.51, 25.05, 121.51) == 0


@pytest.mark.parametrize(
    ("to", "expected"),
    [((1, 0), 0), ((0, 1), 90), ((-1, 0), 180), ((0, -1), 270)],
)
def test_bearing_cardinal_directions(to, expected):
    assert bearing_deg(0, 0, *to) == pytest.approx(expected, abs=0.5)


@pytest.mark.parametrize(
    ("a", "b", "diff"), [(350, 10, 20), (10, 350, 20), (0, 180, 180), (90, 90, 0), (270, 90, 180)]
)
def test_angle_diff_wraps_around(a, b, diff):
    assert angle_diff(a, b) == pytest.approx(diff)


def test_bounding_box_contains_points_at_the_radius():
    box = bounding_box(25.05, 121.51, 500)

    north = (25.05 + 450 / 111_195, 121.51)
    east = (25.05, 121.51 + 450 / (111_195 * 0.906))
    for lat, lon in (north, east):
        assert box.min_lat < lat < box.max_lat
        assert box.min_lon < lon < box.max_lon
    assert box.max_lat - box.min_lat == pytest.approx(2 * 500 / 111_195, rel=0.01)
