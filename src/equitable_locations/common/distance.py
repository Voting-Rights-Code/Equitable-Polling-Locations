import pandas as pd
import geopandas as gpd
import time
from equitable_locations.io.osm import OsmIsochroneGenerator, CoverageError
from typing import Union, List


class DistanceGenerator:
    OUTPUT_COLUMNS = [
        "id_orig",
        "id_dest",
        "distance",
        "county",
        "address",
        "dest_lat",
        "dest_lon",
        "orig_lat",
        "orig_lon",
        "location_type",
        "dest_type",
        "population",
        "hispanic",
        "non-hispanic",
        "white",
        "black",
        "native",
        "asian",
        "pacific_islander",
        "other",
        "multiple_races",
        "weighted_dist",
    ]

    # Distance generator" class. The class should be initialized with a isochrone generator object,
    # list of times, origins dataframe, and a destinations dataframe.
    # The distance generator class should hav a "calc" method which generates a dataframe as
    # output for optimization. Write "save" and "load" methods for the dataframe made with the
    # "calc" method. Optional parameters for initialization include snap origin to road, whether
    # to drop origins with no population, or if minimum time should be used.
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
        self.times = sorted(times, reverse=True)

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

    def calc(self) -> pd.DataFrame:
        # TODO: make agnostic of generator type (straight line, road distance, vs isochrone distance)
        # Perform distance calculation and generate dataframe
        # this should be the main method using configurations to set up the distance calculations

        if self.use_minimum_time:
            temp_min_time_idx = self.find_minimum_time(
                poll_location_type=["polling", "potential"], N_distance_minimum=self.N_distance_minimum
            )
            # make sure more than one time is used in generating distances
            if temp_min_time_idx == len(self.times) - 1:
                print(
                    "Warning: the lowest supplied time was found to satisfy coverage requirements. Increasing the minimum time to the second smallest."
                )
                temp_min_time_idx -= 1
            # TODO: invert minimum time index logic
            min_time_idx = len(self.times) - 1 - temp_min_time_idx
            self.times = self.times[min_time_idx:]

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

        # create a dictionary of all the isochrones for all the times
        # the dataframe with the largest time retains all columns
        self.generate_isochrone_dict()

        # make a geodataframe with all possible combinations by merging the origins with the largest travel times
        gdf_full = origins_gdf.sjoin(self.destination_isochrones[self.times[0]], how="left", predicate="within").drop(
            "index_right", axis=1
        )
        # create a distance column and set to the largest distance
        gdf_full.loc[:, "distance"] = self.times[0]

        # For each additional time, match on point within poly and destination=destination
        for traveltime in self.times[1:]:
            # TODO: Identify why this loop slows down with big dataframes. Seems to be single-threaded
            # see https://stackoverflow.com/questions/54804073/how-can-i-accelerate-a-geopandas-spatial-join
            # https://gis.stackexchange.com/questions/309501/multiprocessing-with-geopandas
            # this spatial join can probably be accomplished by splitting origins_gdf into multiple and comparing
            # each against all of the destinations. Final dataframe should then just be the union.
            print(traveltime)
            working_isochrone = self.destination_isochrones[traveltime]
            gdf_full = gdf_full.sjoin(
                df=working_isochrone.loc[:, ["id_dest", "geometry"]],
                how="left",
                predicate="within",
                on_attribute=["id_dest"],
            )
            # find merged columns and update distance
            gdf_full.loc[gdf_full.loc[:, "index_right"].notna(), "distance"] = traveltime
            # drop "index_right" to clean up
            gdf_full = gdf_full.drop("index_right", axis=1)

        # create other useful columns
        gdf_full["weighted_dist"] = gdf_full["population"] * gdf_full["distance"]

        # downselect to the necessary columns
        gdf_full = gdf_full[self.OUTPUT_COLUMNS]

        # Return the dataframe
        self.optimization_dataframe = gdf_full
        return gdf_full

    def generate_isochrone_dict(self):
        # Generate all isochrones
        # TODO: only generate isochrones with geometry and location ID
        isochrone_dict = {}
        first = True
        for traveltime in self.times:
            gdf = self.isochrone_generator.get_isochrones(
                locations=self.destinations,
                lat_column="dest_lat",
                lon_column="dest_lon",
                travel_time=traveltime,
            )
            if first:
                first = False
            else:
                # downselect columns after the first
                gdf = gdf.loc[:, ["id_dest", "geometry"]]
            isochrone_dict[traveltime] = gdf
        self.destination_isochrones = isochrone_dict

    def save(self, filename):
        # Save the dataframe to a file with the given filename
        self.optimization_dataframe.to_csv(filename, index=False)

    def find_minimum_time(
        self,
        poll_location_type: Union[None, List[str]] = None,
        N_distance_minimum: int = 2,
    ):
        # Find the minimum time from the list of times provided. This should be written using binary search to find the minimum time from the supplied list. This method uses two arguments. The first is a string to filter the poll location type in the destination dataframe. Second, the N distances to each block group. If the smallest time from the provided list, return the next largest and log a warning.
        # Implement binary search to find the minimum time from the list of times

        if poll_location_type is not None:
            filtered_destinations = self.destinations.loc[
                self.destinations.loc[:, "dest_type"].isin(poll_location_type), :
            ]
        else:
            filtered_destinations = self.destinations

        # TODO: flip this logic so sorting not needed here
        processing_times = self.times.copy()
        processing_times.sort()
        left = 0
        right = len(processing_times) - 1
        min_time = None
        min_idx = None
        start = time.time()
        while left <= right:
            mid = (left + right) // 2
            try:
                print(
                    f"Testing index: {mid} for {processing_times[mid]} minutes with {poll_location_type} polling locations"
                )
                gdf = self.isochrone_generator.get_isochrones(
                    locations=filtered_destinations,
                    lat_column="dest_lat",
                    lon_column="dest_lon",
                    travel_time=processing_times[mid],
                )
                # make sure N minimum for each type of poll location type
                if poll_location_type is not None:
                    for location_type in poll_location_type:
                        print(
                            f"Checking coverage for type {location_type} at radius {processing_times[mid]} minutes for a minumum of {N_distance_minimum}"
                        )
                        self.isochrone_generator.check_coverage(
                            origins_df=self.origins,
                            lat_column="orig_lat",
                            lon_column="orig_lon",
                            snap_to_road=self.snap_origin,
                            isochrones_gdf=gdf.loc[gdf.loc[:, "dest_type"] == location_type, :],
                            N=N_distance_minimum,
                        )
                else:
                    self.isochrone_generator.check_coverage(
                        origins_df=self.origins,
                        lat_column="orig_lat",
                        lon_column="orig_lon",
                        snap_to_road=self.snap_origin,
                        isochrones_gdf=gdf,
                        N=N_distance_minimum,
                    )
                min_time = processing_times[mid]
                min_idx = mid
                right = mid - 1
            except CoverageError:
                print(f"CoverageError on {mid}")
                left = mid + 1
            print(f"Processing index {mid} complete, Time Elapsed: {time.time()-start:.2f} seconds")

        if min_time is None:
            raise CoverageError("No appropriate time found")
        print(f"Found minimum: {min_time} (index {min_idx}), Time Elapsed: {time.time()-start:.2f} seconds")

        return min_idx

        # # Filter the destination dataframe based on poll_location_type
        # filtered_destinations = self.destinations[self.destinations['poll_location_type'] == poll_location_type]

        # # Calculate the distances to each block group
        # distances_to_block_groups = self.calculate_distances(filtered_destinations)
