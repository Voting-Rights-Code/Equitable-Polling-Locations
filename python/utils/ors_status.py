'''Verify the OpenRouteService container has loaded the expected state graph.

Pure stdlib. ORS exposes the loaded routing graphs and their source files via
``/ors/v2/status`` — we hit that and confirm the ``source_file`` field matches
the ``<slug>-latest.osm.pbf`` filename we asked for. This catches the silent
"ORS fell back to the bundled Heidelberg demo extract" failure mode.
'''
import json
import urllib.error
import urllib.request


def verify_loaded_state(expected_slug: str, matrix_url: str) -> None:
    '''Hit ``/ors/v2/status`` and confirm the loaded graph matches ``expected_slug``.

    The status URL is derived from ``matrix_url`` by stripping ``/matrix/...``
    and appending ``/status``, so callers can pass whatever ORS base URL they
    already have.

    Args:
        expected_slug: The Geofabrik state slug the caller expected (e.g.
            ``'georgia'``).
        matrix_url: ORS matrix URL (any URL containing ``/matrix/`` works).

    Raises:
        RuntimeError: If the loaded graph's ``source_file`` doesn't match the
            expected ``<slug>-latest.osm.pbf`` filename, OR if the status
            payload is missing the ``source_file`` field entirely (can't
            verify → fail safe).
    '''
    status_url = matrix_url.rsplit('/matrix/', 1)[0] + '/status'
    try:
        with urllib.request.urlopen(status_url, timeout=10) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        # Infrastructure problems (ORS not reachable, garbage response) are
        # surfaced more clearly by the matrix call itself; don't double-report
        # here.
        print(f'verify_loaded_state: could not fetch {status_url}: {exc}; '
              f'proceeding on contract trust')
        return

    expected_filename = f'{expected_slug}-latest.osm.pbf'
    profiles = payload.get('profiles', {})

    for profile_meta in profiles.values():
        source_file = profile_meta.get('source_file')
        if source_file:
            if expected_filename in source_file:
                return
            raise RuntimeError(
                f'ORS has {source_file!r} loaded but expected {expected_filename!r}. '
                f'Stop ORS (ors_down_cli) and rerun with the correct state.'
            )

    raise RuntimeError(
        f'/ors/v2/status returned no source_file field; cannot verify the loaded '
        f'graph matches {expected_filename!r}. This usually means an ORS schema '
        f'change — please file an issue against the driving-distance toolset.'
    )
