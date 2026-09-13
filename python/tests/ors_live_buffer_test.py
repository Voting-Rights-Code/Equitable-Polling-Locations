'''Live-ORS acceptance test for the buffered extract (issue #226).

Regression guard for the silent cross-border distance inflation the buffered
extract fixes. The ticket's WV->PA pair sits just south of the Pennsylvania
line; the efficient route crosses briefly into PA, while a bare single-state WV
graph (missing the PA roads) is *physically unable* to route across the border
and is forced into a long detour that stays inside WV.

The guard asserts the buffered route's geometry crosses **north of the WV/PA
border** — i.e. it actually used Pennsylvania roads. That is the exact capability
#226 restores, and it is unambiguous: a regression that dropped the buffer could
not produce a route north of the line at all. (Distance/duration are a poor
discriminator here — the through-PA route and the in-WV detour are similar
lengths; only crossing the border separates them.)

Gated out of default runs; opt in with:  pytest -m ors_live

Set ORS_BUFFERED_URL to the running buffered-graph ORS matrix endpoint, e.g.
    ORS_BUFFERED_URL=http://localhost:8080/ors/v2/matrix/driving-car
(the directions URL is derived from it). The test skips (never fails) when it is
absent, so it doubles as the executable acceptance procedure.
'''

import os

import pytest

from python.utils.ors_client import query_route_geometry
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

# WV/PA border (Mason-Dixon line) near Morgantown. Both endpoints sit just south
# of it; a route that uses the cross-border shortcut crosses north of it, while
# the in-WV detour the bug forces stays south. (A confirmed buffered run reaches
# ~39.764, i.e. ~5 km into PA.)
WV_PA_BORDER_LAT = 39.7201


def _route_coordinates(matrix_url: str) -> list | None:
    '''Return the WV->PA route polyline via the directions endpoint.

    Args:
        matrix_url: An ORS matrix endpoint URL; the directions URL is derived
            from it.

    Returns:
        A list of ``[longitude, latitude]`` coordinate pairs, or None if ORS
        found no route.
    '''
    directions_url = directions_url_from_matrix_url(matrix_url)
    return query_route_geometry(list(ORIGIN_LON_LAT), list(DEST_LON_LAT), directions_url)


@pytest.mark.ors_live
def test_buffered_route_crosses_into_pennsylvania():
    '''The buffered WV->PA route crosses north of the WV/PA border (uses PA roads).'''
    buffered_url = os.environ.get('ORS_BUFFERED_URL')
    if not buffered_url:
        pytest.skip(
            'Set ORS_BUFFERED_URL to a running buffered-graph ORS matrix endpoint '
            'to run this acceptance test.'
        )

    coordinates = _route_coordinates(buffered_url)
    assert coordinates, (
        'Buffered ORS returned no route geometry for the WV->PA pair; confirm '
        'the graph is built and the endpoints snap to roads.'
    )

    northernmost_lat = max(point[1] for point in coordinates)
    assert northernmost_lat > WV_PA_BORDER_LAT, (
        f'Route northernmost latitude {northernmost_lat:.4f} does not cross the '
        f'WV/PA border ({WV_PA_BORDER_LAT}) — the buffered graph is not routing '
        f'through Pennsylvania (this looks like the in-WV detour).'
    )
