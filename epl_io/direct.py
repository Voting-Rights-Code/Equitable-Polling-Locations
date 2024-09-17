from epl_io import PROJECT_ROOT
from pyproj import CRS

print(PROJECT_ROOT)
class BaseDistanceCalculator:
    EXTERNAL_CRS = CRS.from_epsg(4326)  # same as WGS 84

    def __init__(self):
        self.distance_dir = PROJECT_ROOT / "untracked" / "distance_files"
        self.distance_dir.mkdir(parents=True, exist_ok=True)

        self.database_path = self.distance_dir / "default.db"

    def calc(origin_latlon: tuple[float, float], destination_latlon: tuple[float, float]):
        raise NotImplementedError("Override sample method from base class")

    def save_distance(self, origin_latlon: tuple[float, float], destination_latlon: tuple[float, float]):
        return None
        # TODO: add database interaction - write results

    def load_distance(self, origin_latlon: tuple[float, float], destination_latlon: tuple[float, float]):
        if False:
            pass
            # TODO: add database interaction - read results
        else:
            return None

    def get_distance(self, origin_latlon: tuple[float, float], destination_latlon: tuple[float, float]):
        # Attempt to load the shapefile

        distance = self.load_distance(origin_latlon=origin_latlon, destination_latlon=destination_latlon)

        # If the file does not exist, generate and save the result
        if distance is None:
            distance = self.calc(origin_latlon=origin_latlon, destination_latlon=destination_latlon)
            self.save_distance(origin_latlon=origin_latlon, destination_latlon=destination_latlon)

        return distance
