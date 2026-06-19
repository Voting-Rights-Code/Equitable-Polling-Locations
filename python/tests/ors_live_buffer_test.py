'''Live-ORS acceptance test for the buffered extract (issue #226).

Regression guard for the silent cross-border distance inflation the buffered
extract fixes. The ticket's WV->PA pair sits just south of the Pennsylvania
line: the correct route crosses briefly into PA (~15 min), while a bare
single-state WV graph (missing the PA roads) forces a long detour south through
Morgantown (~30+ min). On a state+50 km buffered graph the direct cross-border
road exists, so the routed distance stays short.

This guard is **self-contained**: it queries the running (buffered) ORS once and
asserts the WV->PA route is short enough to prove it took the cross-border
shortcut. A regression that dropped the buffer would balloon the route back to
the in-WV detour and trip the ceiling — no separate single-state graph needed.

Gated out of default runs; opt in with:  pytest -m ors_live

Set ORS_BUFFERED_URL to the running buffered-graph ORS matrix endpoint, e.g.
    ORS_BUFFERED_URL=http://localhost:8080/ors/v2/matrix/driving-car
(the directions URL is derived from it). Optionally also set
ORS_SINGLE_STATE_BASELINE_M to additionally assert the literal
"buffered < single-state" comparison against a recorded bare-graph distance.
The test skips (never fails) when ORS_BUFFERED_URL is absent, so it doubles as
the executable acceptance procedure.
'''

import os

import pytest

from python.utils.ors_client import query_directions
from python.utils.ors_url import directions_url_from_matrix_url

# Geocoded once and hardcoded (do not geocode at runtime). Coordinates are
# [longitude, latitude]. ORS snaps each to the nearest routable OSM road, so
# rooftop precision is not required; confirm both route on the first live run.
#   Origin: 1732 Fort Martin Rd, Maidsville, WV 26541 (address geocode).
#     OSM's Fort Martin Road itself runs near (-79.952, 39.705); use that as a
#     fallback if the rooftop estimate below fails to route.
#   Dest:   124 Eden Church Rd, Morgantown, WV 26508 (US Census rooftop geocode).
ORIGIN_LON_LAT = (-79.9277, 39.7106)
DEST_LON_LAT = (-79.9007, 39.7054)

# The cross-border (through-PA) route is ~15 min; the in-WV detour the bug forces
# is ~30+ min. This ceiling sits in that gap: comfortably above the shortcut,
# well below the detour. Confirm/tune against the real distance on the first live
# run (the failure message prints the observed metres).
MAX_SHORTCUT_ROUTE_M = 20_000

# When a recorded single-state baseline is supplied, the buffered route must be
# at most this fraction of it.
MAX_BUFFERED_FRACTION = 0.8


def _route_meters(matrix_url: str) -> float | None:
    '''Return the WV->PA driving distance in metres via the directions endpoint.

    Args:
        matrix_url: An ORS matrix endpoint URL; the directions URL is derived
            from it.

    Returns:
        The routed distance in metres, or None if ORS found no route.
    '''
    directions_url = directions_url_from_matrix_url(matrix_url)
    return query_directions(list(ORIGIN_LON_LAT), list(DEST_LON_LAT), directions_url)


@pytest.mark.ors_live
def test_buffered_route_takes_cross_border_shortcut():
    '''The buffered WV->PA route is short enough to prove it crossed into PA.'''
    buffered_url = os.environ.get('ORS_BUFFERED_URL')
    if not buffered_url:
        pytest.skip(
            'Set ORS_BUFFERED_URL to a running buffered-graph ORS matrix endpoint '
            'to run this acceptance test.'
        )

    buffered_m = _route_meters(buffered_url)
    assert buffered_m is not None, (
        'Buffered ORS returned no route for the WV->PA pair; confirm the graph '
        'is built and the endpoints snap to roads.'
    )
    assert buffered_m < MAX_SHORTCUT_ROUTE_M, (
        f'Buffered WV->PA route is {buffered_m:.0f} m, not below the '
        f'{MAX_SHORTCUT_ROUTE_M} m shortcut ceiling — it looks like the long '
        f'in-WV detour, i.e. the buffer is not taking effect.'
    )

    # Optional stronger check: the literal before/after against a recorded
    # single-state distance, if one is supplied.
    baseline_env = os.environ.get('ORS_SINGLE_STATE_BASELINE_M')
    if baseline_env:
        single_state_m = float(baseline_env)
        assert buffered_m < single_state_m * MAX_BUFFERED_FRACTION, (
            f'Buffered route {buffered_m:.0f} m is not materially shorter than '
            f'the recorded single-state route {single_state_m:.0f} m '
            f'(need < {MAX_BUFFERED_FRACTION:.0%}).'
        )
