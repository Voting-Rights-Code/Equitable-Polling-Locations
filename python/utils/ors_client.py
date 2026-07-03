'''Thin HTTP wrapper around the OpenRouteService matrix and directions endpoints.

This module exposes only the wire-level interactions with ORS. Higher-level
concerns (batching, retries, snapping) live in driving_distance_matrix.py.
'''
import json

import requests


HTTP_TIMEOUT_SECONDS = 60


class OrsMatrixError(Exception):
    '''Raised when the ORS matrix endpoint returns an error response.'''


_METRIC_TO_RESPONSE_KEY = {'distance': 'distances', 'duration': 'durations'}


def query_matrix(locations, sources, dests, server, *, key=None, metrics=('distance', 'duration')):
    '''POST a matrix query to ORS and return one result grid per requested metric.

    Args:
        locations: All location coordinates as ``[longitude, latitude]`` pairs.
        sources: Indices into ``locations`` for origins.
        dests: Indices into ``locations`` for destinations.
        server: ORS matrix endpoint URL.
        key: Optional ORS API key (required only for the public cloud endpoint).
        metrics: Metrics to request (subset of ``'distance'``, ``'duration'``).
            Both are returned in a single ORS call at no meaningful extra cost.

    Returns:
        A dict mapping each requested metric name to its grid: a list with one
        row per source, each row having one entry per destination. E.g.
        ``{'distance': [[...]], 'duration': [[...]]}``.

    Raises:
        OrsMatrixError: When ORS omits a requested metric's grid (error response).
    '''
    body = {
        'locations': locations,
        'destinations': dests,
        'metrics': list(metrics),
        'sources': sources,
    }
    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Content-Type': 'application/json; charset=utf-8',
    }
    if key:
        headers['Authorization'] = key

    response = requests.post(server, json=body, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    parsed = json.loads(response.text)
    result = {}
    for metric in metrics:
        response_key = _METRIC_TO_RESPONSE_KEY[metric]
        if response_key not in parsed:
            raise OrsMatrixError(f'ORS matrix call failed: {parsed.get("error", parsed)}')
        result[metric] = parsed[response_key]
    return result


def query_directions(source, dest, server):
    '''Return ``(distance_m, duration_s)`` between ``source`` and ``dest``.

    Uses the ORS single-pair directions endpoint.

    Args:
        source: ``[longitude, latitude]`` for the origin.
        dest: ``[longitude, latitude]`` for the destination.
        server: ORS directions endpoint URL.

    Returns:
        A ``(distance_m, duration_s)`` tuple, or ``None`` if ORS returned an
        error (e.g. no route found) or a malformed success payload lacking the
        expected ``features[0].properties.segments[0]`` path.
    '''
    url = f'{server}?start={source[0]},{source[1]}&end={dest[0]},{dest[1]}'
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    parsed = json.loads(response.text)
    if 'error' in parsed:
        return None
    try:
        segment = parsed['features'][0]['properties']['segments'][0]
        return segment['distance'], segment['duration']
    except (KeyError, IndexError):
        return None


def query_route_geometry(source, dest, server):
    '''Return the route polyline between ``source`` and ``dest``.

    Uses the ORS single-pair directions endpoint.

    Args:
        source: ``[longitude, latitude]`` for the origin.
        dest: ``[longitude, latitude]`` for the destination.
        server: ORS directions endpoint URL.

    Returns:
        The route geometry as a list of ``[longitude, latitude]`` coordinate
        pairs, or ``None`` if ORS returned an error (e.g. no route found) or a
        payload lacking the expected ``features[0].geometry.coordinates`` path.
    '''
    url = f'{server}?start={source[0]},{source[1]}&end={dest[0]},{dest[1]}'
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    parsed = json.loads(response.text)
    if 'error' in parsed:
        return None
    try:
        return parsed['features'][0]['geometry']['coordinates']
    except (KeyError, IndexError):
        return None
