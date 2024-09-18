from epl_io.direct import BaseDistanceCalculator
from haversine import haversine, Unit


class HaversineDistanceCalculator(BaseDistanceCalculator):
    def __init__(self):
        super().__init__()

    def calc(self, origin_latlon: tuple[float, float], destination_latlon: tuple[float, float]):
        return haversine(origin_latlon, destination_latlon, unit=Unit.METERS)
