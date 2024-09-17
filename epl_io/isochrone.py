from shapely import to_geojson, from_geojson
from pyproj import CRS
from epl_io import PROJECT_ROOT
import pandas as pd


class CoverageError(Exception):
    """Exception raised when isochrone coverage check fails."""

    def __init__(self, uncovered_locations=0, message=None):
        if message is None:
            message = f"{uncovered_locations} locations are not covered by the required number of isochrones"
        self.message = message
        super().__init__(self.message)


class BaseIsochroneGenerator:
    # A base isochrone generator class which provides methods for saving and loading shapefiles from disk if they exist.
    EXTERNAL_CRS = CRS.from_epsg(4326)  # same as WGS 84

    def __init__(self):
        self.isochrone_dir = PROJECT_ROOT / "untracked" / "isochrone_files"
        self.isochrone_dir.mkdir(parents=True, exist_ok=True)

    def save_isochrone(self, filename: str, shape):
        filepath = self.isochrone_dir / filename

        # To GeoJSON
        filepath.write_text(to_geojson(shape))

    def load_isochrone(self, filename: str):
        filepath = self.isochrone_dir / filename
        if filepath.exists():
            return from_geojson(filepath.read_text())
        else:
            return None

    def get_isochrone(self, lat, lon, travel_time: int):
        # Attempt to load the shapefile
        filename = f"{self.travel_method}_{lat:.4f}_{lon:.4f}_{travel_time}.geojson"
        isochrone = self.load_isochrone(filename)

        # If the file does not exist, generate and save the result
        if isochrone is None:
            isochrone = self.generate_isochrone(lat, lon, travel_time)
            self.save_isochrone(filename, isochrone)

        return isochrone

    def get_isochrones(
        self, locations: pd.core.frame.DataFrame, lat_column: str, lon_column: str, travel_time: int = 5
    ):
        raise NotImplementedError("Override base function")

    def generate_isochrone(self, lat, lon, travel_time):
        raise NotImplementedError("Override base function")
