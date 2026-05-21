'''Thin HTTP wrapper around the OpenRouteService matrix and directions endpoints.

This module exposes only the wire-level interactions with ORS. Higher-level
concerns (batching, retries, snapping) live in driving_distance_matrix.py.
'''
import json

import requests


HTTP_TIMEOUT_SECONDS = 60


class OrsMatrixError(Exception):
    '''Raised when the ORS matrix endpoint returns an error response.'''


def query_matrix(locations, sources, dests, server, *, key=None, metric='distance'):
    '''POST a matrix query to ORS and return the distance rows.

    Args:
        locations: All location coordinates as ``[longitude, latitude]`` pairs.
        sources: Indices into ``locations`` for origins.
        dests: Indices into ``locations`` for destinations.
        server: ORS matrix endpoint URL.
        key: Optional ORS API key (required only for the public cloud endpoint).
        metric: Metric to request from ORS (``'distance'`` or ``'duration'``).

    Returns:
        The ``distances`` field of the ORS response: a list with one row per
        source, each row having one entry per destination.

    Raises:
        OrsMatrixError: When ORS returns an error response (no ``distances`` field).
    '''
    body = {
        'locations': locations,
        'destinations': dests,
        'metrics': [metric],
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
    if 'distances' not in parsed:
        raise OrsMatrixError(f'ORS matrix call failed: {parsed.get("error", parsed)}')
    return parsed['distances']


def query_directions(source, dest, server):
    '''Return the driving distance in meters between ``source`` and ``dest``.

    Uses the ORS single-pair directions endpoint.

    Args:
        source: ``[longitude, latitude]`` for the origin.
        dest: ``[longitude, latitude]`` for the destination.
        server: ORS directions endpoint URL.

    Returns:
        Driving distance in meters, or ``None`` if ORS returned an error
        (e.g. no route found).
    '''
    url = f'{server}?start={source[0]},{source[1]}&end={dest[0]},{dest[1]}'
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    parsed = json.loads(response.text)
    if 'error' in parsed:
        return None
    return parsed['features'][0]['properties']['segments'][0]['distance']
