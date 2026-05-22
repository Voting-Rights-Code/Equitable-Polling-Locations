'''Geofabrik state OSM extract helpers (download + slug table).

Pure stdlib so the module is importable on the host without the project's
conda env being installed. ORS lifecycle scripts run on the host as file
paths (not via ``python -m``) so they can import this module without
triggering ``python/__init__.py``'s numpy import.
'''
import os
import urllib.request


GEOFABRIK_BASE_URL = 'https://download.geofabrik.de/north-america/us'

# 50 states + DC. Slugs are the lowercase, hyphen-joined forms used in
# Geofabrik download paths (`https://download.geofabrik.de/north-america/us/
# <slug>-latest.osm.pbf`). Territories (Puerto Rico, Guam, etc.) live under
# different Geofabrik paths and are not supported in v1.
GEOFABRIK_STATE_SLUGS = {
    'alabama', 'alaska', 'arizona', 'arkansas', 'california',
    'colorado', 'connecticut', 'delaware', 'district-of-columbia',
    'florida', 'georgia', 'hawaii', 'idaho', 'illinois',
    'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new-hampshire', 'new-jersey', 'new-mexico', 'new-york',
    'north-carolina', 'north-dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode-island', 'south-carolina', 'south-dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia',
    'washington', 'west-virginia', 'wisconsin', 'wyoming',
}

ORS_DATA_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', 'datasets', 'openrouteservice',
    )
)


def geofabrik_url(slug: str) -> str:
    '''Return the Geofabrik download URL for a state slug.

    Args:
        slug: Geofabrik state slug (e.g. ``'georgia'``, ``'new-york'``).

    Returns:
        The HTTPS URL for ``<slug>-latest.osm.pbf`` on Geofabrik.

    Raises:
        ValueError: If ``slug`` is not in ``GEOFABRIK_STATE_SLUGS``.
    '''
    if slug not in GEOFABRIK_STATE_SLUGS:
        raise ValueError(f'unknown state slug: {slug!r}')
    return f'{GEOFABRIK_BASE_URL}/{slug}-latest.osm.pbf'


def pbf_path(slug: str) -> str:
    '''Return the local path where ``<slug>-latest.osm.pbf`` lives.

    Args:
        slug: Geofabrik state slug.

    Returns:
        Absolute filesystem path under ``ORS_DATA_DIR``.
    '''
    return os.path.join(ORS_DATA_DIR, f'{slug}-latest.osm.pbf')


def download_pbf_if_missing(slug: str) -> str:
    '''Download the state's .pbf to ``ORS_DATA_DIR`` if it isn't already there.

    Downloads to a ``<target>.partial`` sibling and atomically renames on
    success, so a failed/cancelled download cannot leave a truncated .pbf
    that future runs would mistake for a complete file.

    Prints a clear message before the download starts (so the user isn't
    surprised by a hundreds-of-MB network operation) and a confirmation
    after.

    Args:
        slug: Geofabrik state slug.

    Returns:
        Absolute filesystem path to the .pbf (whether downloaded now or
        pre-existing).

    Raises:
        ValueError: If ``slug`` is not a known state slug.
    '''
    if slug not in GEOFABRIK_STATE_SLUGS:
        raise ValueError(f'unknown state slug: {slug!r}')
    target = pbf_path(slug)
    if os.path.exists(target):
        return target
    os.makedirs(ORS_DATA_DIR, exist_ok=True)
    url = geofabrik_url(slug)
    print(f'Downloading {slug}-latest.osm.pbf from Geofabrik (this is hundreds of MB)...')
    partial = f'{target}.partial'
    urllib.request.urlretrieve(url, partial)
    os.replace(partial, target)
    print(f'Done: {os.path.getsize(target):,} bytes written to {target}')
    return target
