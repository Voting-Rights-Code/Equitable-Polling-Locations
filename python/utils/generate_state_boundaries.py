"""One-time generator for datasets/boundaries/us_states.geojson.

Downloads the US Census cartographic state boundaries, keeps the 50 states + DC,
renames the postal column to ``postal``, and writes a compact EPSG:4326 GeoJSON.
Run once; the output is committed. Not used at runtime.
"""

import io
import zipfile
import urllib.request

import geopandas as gpd

from python.utils.ors_setup import STATE_CODE_TO_SLUG

CENSUS_STATES_ZIP_URL = (
    'https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip'
)
OUTPUT_PATH = 'datasets/boundaries/us_states.geojson'


def main() -> None:
    """Download, filter, and write the committed boundary GeoJSON.

    Downloads the Census ``cb_2023_us_state_20m`` cartographic boundary ZIP,
    extracts it to ``/tmp``, filters to the 50 states + DC (matching
    :data:`~python.utils.ors_setup.STATE_CODE_TO_SLUG` keys), renames the
    ``STUSPS`` column to ``postal``, reprojects to EPSG:4326, and writes to
    :data:`OUTPUT_PATH`.
    """
    print(f'Downloading Census state boundaries from {CENSUS_STATES_ZIP_URL} ...')
    with urllib.request.urlopen(CENSUS_STATES_ZIP_URL) as response:
        archive_bytes = response.read()
    print(f'Downloaded {len(archive_bytes):,} bytes; extracting ...')
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        archive.extractall('/tmp/cb_2023_us_state_20m')

    states = gpd.read_file('/tmp/cb_2023_us_state_20m/cb_2023_us_state_20m.shp')
    states = states[states['STUSPS'].isin(STATE_CODE_TO_SLUG.keys())].copy()
    states = states.rename(columns={'STUSPS': 'postal'})[['postal', 'geometry']]
    states = states.to_crs(4326)
    states.to_file(OUTPUT_PATH, driver='GeoJSON')
    print(f'Wrote {len(states)} features to {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
