'''Live-ORS acceptance test for the buffered extract (issue #226).

Regression guard for the silent cross-border distance inflation the buffered
extract fixes. The ticket's WV->PA pair sits just south of the Pennsylvania
line, separated east-west: the direct connection runs through PA, while a bare
single-state WV graph (missing the PA roads) forces a long southern detour. On a
state+50 km buffered graph the direct road exists, so the routed distance is
materially shorter.

Gated out of default runs; opt in with:  pytest -m ors_live

Operational prerequisites (see the issue #226 host runbook):
  * Boot ORS on the WV-buffered graph and export its matrix URL as
    ORS_BUFFERED_URL, e.g.
        ORS_BUFFERED_URL=http://localhost:8080/ors/v2/matrix/driving-car
    (the directions URL is derived from it). The test skips if it is unset.
  * Provide the single-state baseline to compare against, EITHER:
      - ORS_SINGLE_STATE_URL: a second ORS booted on the bare WV graph, OR
      - ORS_SINGLE_STATE_BASELINE_M: the single-state route distance in metres,
        recorded from an earlier bare-WV run (the tooling now always builds the
        buffered graph, so a recorded baseline is usually the practical input).
    The test skips if neither is provided.

Because every missing prerequisite is a clean skip (never a failure), this file
doubles as the executable acceptance procedure until the two graphs exist.
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

# The buffered (through-PA) route must be at most this fraction of the
# single-state (all-WV detour) route to count as "materially shorter".
# Conservative floor; tighten once the real ratio is observed on the first run.
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
def test_buffered_route_beats_single_state():
    '''Buffered WV->PA route is materially shorter than the single-state route.'''
    # Gate on configuration before any network I/O so a misconfigured run skips
    # instantly instead of hanging on a connection.
    buffered_url = os.environ.get('ORS_BUFFERED_URL')
    if not buffered_url:
        pytest.skip(
            'Set ORS_BUFFERED_URL to a running buffered-graph ORS matrix endpoint '
            'to run this acceptance test.'
        )

    single_state_url = os.environ.get('ORS_SINGLE_STATE_URL')
    baseline_env = os.environ.get('ORS_SINGLE_STATE_BASELINE_M')
    if not single_state_url and not baseline_env:
        pytest.skip(
            'Provide ORS_SINGLE_STATE_URL (a second ORS on the bare WV graph) or '
            'ORS_SINGLE_STATE_BASELINE_M (the recorded single-state distance in '
            'metres) to compare against.'
        )

    buffered_m = _route_meters(buffered_url)
    assert buffered_m is not None, (
        'Buffered ORS returned no route for the WV->PA pair; confirm the graph '
        'is built and the endpoints snap to roads.'
    )

    if single_state_url:
        single_state_m = _route_meters(single_state_url)
        assert single_state_m is not None, (
            'Single-state ORS returned no route for the WV->PA pair.'
        )
    else:
        single_state_m = float(baseline_env)

    assert buffered_m < single_state_m * MAX_BUFFERED_FRACTION, (
        f'Buffered route {buffered_m:.0f} m is not materially shorter than the '
        f'single-state route {single_state_m:.0f} m '
        f'(need < {MAX_BUFFERED_FRACTION:.0%} of it).'
    )
