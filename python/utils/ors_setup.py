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

# 2-letter US postal codes → Geofabrik state slug. Used to derive the state
# from a PollingModelConfig `location` field that follows the `<Name>_<ST>`
# convention (e.g. `Tarrant_County_TX` → `'texas'`). 50 states + DC; not all
# postal codes are covered (PR, GU, etc. live under non-US Geofabrik paths).
STATE_CODE_TO_SLUG = {
    'AL': 'alabama', 'AK': 'alaska', 'AZ': 'arizona', 'AR': 'arkansas',
    'CA': 'california', 'CO': 'colorado', 'CT': 'connecticut', 'DE': 'delaware',
    'DC': 'district-of-columbia', 'FL': 'florida', 'GA': 'georgia',
    'HI': 'hawaii', 'ID': 'idaho', 'IL': 'illinois', 'IN': 'indiana',
    'IA': 'iowa', 'KS': 'kansas', 'KY': 'kentucky', 'LA': 'louisiana',
    'ME': 'maine', 'MD': 'maryland', 'MA': 'massachusetts', 'MI': 'michigan',
    'MN': 'minnesota', 'MS': 'mississippi', 'MO': 'missouri', 'MT': 'montana',
    'NE': 'nebraska', 'NV': 'nevada', 'NH': 'new-hampshire', 'NJ': 'new-jersey',
    'NM': 'new-mexico', 'NY': 'new-york', 'NC': 'north-carolina',
    'ND': 'north-dakota', 'OH': 'ohio', 'OK': 'oklahoma', 'OR': 'oregon',
    'PA': 'pennsylvania', 'RI': 'rhode-island', 'SC': 'south-carolina',
    'SD': 'south-dakota', 'TN': 'tennessee', 'TX': 'texas', 'UT': 'utah',
    'VT': 'vermont', 'VA': 'virginia', 'WA': 'washington', 'WV': 'west-virginia',
    'WI': 'wisconsin', 'WY': 'wyoming',
}

ORS_DATA_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', 'datasets', 'openrouteservice',
    )
)


def buffer_polygon_path(slug: str) -> str:
    '''Return the path to the buffer-polygon GeoJSON for a state slug.

    Args:
        slug: Geofabrik state slug.

    Returns:
        Absolute filesystem path under ``ORS_DATA_DIR``.
    '''
    return os.path.join(ORS_DATA_DIR, f'{slug}-buffer.geojson')


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


def state_slug_from_location(location: str) -> str:
    '''Derive a Geofabrik state slug from a config ``location`` field.

    Splits ``location`` on ``_``, treats the last segment as a 2-letter US
    postal code (uppercase), and maps via :data:`STATE_CODE_TO_SLUG`.

    Args:
        location: A PollingModelConfig location string, e.g.
            ``'Gwinnett_GA'`` or ``'Tarrant_County_TX'``.

    Returns:
        The Geofabrik state slug (e.g. ``'georgia'``, ``'texas'``).

    Raises:
        ValueError: If the last underscore-delimited segment is not exactly
            two uppercase characters, or is not a known US postal code.
    '''
    if '_' not in location:
        raise ValueError(
            f'location {location!r} has no 2-letter state code suffix; '
            f"expected the form '<Name>_<ST>' (e.g. 'Gwinnett_GA')"
        )
    suffix = location.rsplit('_', 1)[1]
    if len(suffix) != 2 or not suffix.isupper() or not suffix.isalpha():
        raise ValueError(
            f'location {location!r} has no 2-letter state code suffix; '
            f"expected the form '<Name>_<ST>' (e.g. 'Gwinnett_GA')"
        )
    if suffix not in STATE_CODE_TO_SLUG:
        raise ValueError(
            f'location {location!r} ends in unknown state code {suffix!r} '
            f'(50 states + DC supported; territories like PR/GU are not)'
        )
    return STATE_CODE_TO_SLUG[suffix]


def location_from_config_file(config_path: str) -> str:
    '''Read just the ``location:`` field from a PollingModelConfig YAML.

    Stdlib-only: scans line-by-line for a column-0 ``location:`` key. Avoids
    loading PollingModelConfig from ``run.py`` (would pull in pandas/numpy
    via ``python/__init__.py`` and break host-side use without project deps).

    Indented occurrences of ``location:`` are skipped — PollingModelConfig
    configs are flat, but defensive line-position filtering keeps the parser
    robust against future nested keys.

    Args:
        config_path: Filesystem path to a PollingModelConfig YAML file.

    Returns:
        The location value, with surrounding quotes and trailing
        ``# ...`` comments stripped.

    Raises:
        ValueError: If the file cannot be read or has no top-level
            ``location:`` line.
    '''
    try:
        with open(config_path, 'r', encoding='utf-8') as handle:
            lines = handle.readlines()
    except OSError as exc:
        raise ValueError(f'could not read config {config_path!r}: {exc}') from exc
    for raw_line in lines:
        if not raw_line.startswith('location:'):
            continue
        value = raw_line[len('location:'):]
        if '#' in value:
            value = value.split('#', 1)[0]
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        return value
    raise ValueError(f'no top-level location: line in {config_path!r}')
