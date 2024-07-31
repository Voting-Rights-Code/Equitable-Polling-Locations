import pandas as pd
import geopandas as gpd
import time
from equitable_locations.io.osm import OsmIsochroneGenerator, CoverageError
from typing import Union


class DistanceGenerator:
    # Distance generator" class. The class should be initialized with a isochrone generator object, list of times, origins dataframe, and a destinations dataframe. The distance generator class should hav a "calc" method which generates a dataframe as output for optimization. Write "save" and "load" methods for the dataframe made with the "calc" method. Optional parameters for initialization include snap origin to road, whether to drop origins with no population, or if minimum time should be used.
    def __init__(
        self,
        isochrone_generator: OsmIsochroneGenerator,
        times,
        origins,
        destinations,
        snap_origin=True,
        drop_origins=True,
        use_minimum_time=False,
        N_distance_minimum: int = 2,
    ):
        self.isochrone_generator = isochrone_generator

        if len(times) > len(set(times)):
            raise ValueError("Duplicate times supplied.")
        self.times = times
        self.times.sort()

        self.destinations = destinations.copy()
        self.origins = origins.copy()
        self.drop_origins = drop_origins
        # minimum distance calculation parameters
        self.snap_origin = snap_origin
        self.use_minimum_time = use_minimum_time
        self.N_distance_minimum = N_distance_minimum

        if drop_origins:
            # only look at blocks with measured population
            self.origins = self.origins.loc[self.origins.loc[:, "population"] > 0, :]

    def calc(self):
        # TODO: make agnostic of generator type (straight line, road distance, vs isochrone distance)

        if self.use_minimum_time:
            min_time_idx = self.find_minimum_time(
                poll_location_type="polling", N_distance_minimum=self.N_distance_minimum
            )
            # make sure more than one time is used in generating distances
            if min_time_idx == 0:
                print(
                    "Warning: the lowest supplied time was found to satisfy coverage requirements. Increasing the minimum time to the second smallest."
                )
                min_time_idx = 1
            # end is exclusive so adding 1
            self.times = self.times[0 : min_time_idx + 1]

        # configure origin geometry
        lat_column = "orig_lat"
        lon_column = "orig_lon"
        if self.snap_origin:
            origins_gdf = self.isochrone_generator.snap_to_road(
                self.origins, lat_column=lat_column, lon_column=lon_column
            )
        else:
            origins_gdf = gpd.GeoDataFrame(
                self.origins,
                geometry=gpd.points_from_xy(self.origins[lon_column], self.origins[lat_column]),
                crs=self.isochrone_generator.EXTERNAL_CRS,
            )

        # Generate all isochrones
        isochrone_list = []
        for time in self.times:
            gdf = self.isochrone_generator.get_isochrones(
                locations=self.destinations,
                lat_column="dest_lat",
                lon_column="dest_lon",
                travel_time=time,
            )
            isochrone_list.append[gdf]
        self.destination_isochrones = isochrone_list

        gdf_full = origins_gdf.sjoin(isochrone_list[-1], how="left", predicate="within")

        # Perform distance calculation and generate dataframe
        # this should be the main method using configurations to set up the distance calculations
        # Return the dataframe
        pass
        # if self.use_minimum_time:

    def save(self, filename):
        # Save the dataframe to a file with the given filename
        self.optimization_dataframe.to_csv(filename, index=False)

    def load(self, filename):
        # Load the dataframe from the file with the given filename
        return pd.read_csv(filename)

    def find_minimum_time(
        self,
        poll_location_type: Union[None, str] = None,
        N_distance_minimum: int = 2,
    ):
        # Find the minimum time from the list of times provided. This should be written using binary search to find the minimum time from the supplied list. This method uses two arguments. The first is a string to filter the poll location type in the destination dataframe. Second, the N distances to each block group. If the smallest time from the provided list, return the next largest and log a warning.
        # Implement binary search to find the minimum time from the list of times

        if poll_location_type is not None:
            filtered_destinations = df_polling = self.destinations.loc[
                self.destinations.loc[:, "dest_type"] == poll_location_type, :
            ]
        else:
            filtered_destinations = self.destinations

        processing_times = self.times.copy()
        processing_times.sort()
        low = 0
        high = len(processing_times) - 1
        min_time = None
        start = time.time()
        while low <= high:
            mid = (low + high) // 2
            try:
                print(f"Testing index: {mid} for {processing_times[mid]} minutes")
                gdf = self.isochrone_generator.get_isochrones(
                    locations=filtered_destinations,
                    lat_column="dest_lat",
                    lon_column="dest_lon",
                    travel_time=processing_times[mid],
                )
                self.isochrone_generator.check_coverage(
                    origins_df=self.origins,
                    lat_column="orig_lat",
                    lon_column="orig_lon",
                    snap_to_road=self.snap_origin,
                    isochrones_gdf=gdf,
                    N=N_distance_minimum,
                )
                min_time = processing_times[mid]
                high = mid - 1
            except CoverageError:
                print(f"CoverageError on {mid}")
                low = mid + 1
            print(f"Processing index {mid} complete, Time Elapsed: {time.time()-start:.2f} seconds")

        if min_time is None:
            raise CoverageError("No appropriate time found")

        return mid

        # # Filter the destination dataframe based on poll_location_type
        # filtered_destinations = self.destinations[self.destinations['poll_location_type'] == poll_location_type]

        # # Calculate the distances to each block group
        # distances_to_block_groups = self.calculate_distances(filtered_destinations)

    def calculate_distances(self, destinations):
        pass
        # Calculate distances to each block group
        # Return the distances
        # Distance calculation - initial merge with largest time isochrones for full set. Each subsequent time, conduct a merge to update only the selected rows. If not feasible, iterate through all destinations and update dataframe
