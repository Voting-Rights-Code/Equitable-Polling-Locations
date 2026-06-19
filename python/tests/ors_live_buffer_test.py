'''Live-ORS acceptance test for the buffered extract (issue #226).

Requires a running ORS instance and BOTH a single-state and a buffered WV graph.
Excluded from default runs; opt in with: pytest -m ors_live
Endpoints are the ticket's WV->PA shortcut (15 min through PA vs 30+ min in-state).
'''

import pytest

# CONFIRM coordinates (geocode once, hardcode):
ORIGIN_LON_LAT = (-79.99, 39.69)   # 1732 Fort Martin Rd, Maidsville, WV  (PLACEHOLDER — confirm)
DEST_LON_LAT = (-79.93, 39.60)     # 124 Eden Church Rd, Morgantown, WV   (PLACEHOLDER — confirm)


@pytest.mark.ors_live
def test_buffered_route_beats_single_state():
    '''The buffered graph must return a materially shorter WV->PA route.'''
    pytest.skip(
        'Manual live-ORS test: build the single-state WV graph, record the route; '
        'build the WV-buffered graph, record the route; assert buffered << single-state. '
        'Wire to ors_client once the two graphs are available and coordinates confirmed.'
    )
