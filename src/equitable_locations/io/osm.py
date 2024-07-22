import time

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString, Point
from pathlib import Path
from pyproj import CRS
import concurrent.futures
import os


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
        self.isochrone_dir = Path(__file__).resolve().parent / "untracked" / "isochrone_files"
        self.isochrone_dir.mkdir(parents=True, exist_ok=True)

    def save_shapefile(self, filename, shape):
        pass
        # filepath = self.isochrone_dir / filename
        # gdf.to_file(filepath)

    def load_shapefile(self, filename):
        return None
        # filepath = self.temp_dir / filename
        # if filepath.exists():
        #     return gpd.read_file(filepath)
        # else:
        #     return None

    def get_isochrones(self, locations, travel_time):
        # get an array of isochrone geometry objects for the given array of locations
        pass


# create an OSM isochrone generator class inheriting from the base isochrone generator class
class OsmIsochroneGenerator(BaseIsochroneGenerator):
    def __init__(
        self, censusdata, travel_times, travel_method="drive", isochrone_buffer_m=304.8, county_buffer_m=10000
    ):
        super().__init__()
        self.censusdata = censusdata
        self.travel_method = travel_method
        self.travel_times = travel_times

        # update base folder for isochrone data by state and county
        state_folder = censusdata.state_name.replace(" ", "_")
        county_folder = censusdata.county_name.replace(" ", "_")
        self.isochrone_dir = self.isochrone_dir / state_folder / county_folder

        self.place = {"county": censusdata.county_name, "state": censusdata.state_name}
        self.network_type = travel_method
        self.isochrone_buffer_m = isochrone_buffer_m

        self.load_osm_data(county_buffer_m)

    def load_osm_data(self, buffer_m):
        # Get a shapefile of the county specified by self.place. expand the shapefile with a radius of 5 miles.

        # Geocode the place to get the geometry
        place_gdf = ox.geocode_to_gdf(self.place)

        # identify and store the crs to use for the county
        # this will be used for internal calculations for all buffers
        self.internal_crs = place_gdf.estimate_utm_crs()

        place_gdf_buffer = (
            place_gdf.to_crs(self.internal_crs)
            .buffer(buffer_m, cap_style="round", join_style="round")
            .to_crs(OsmIsochroneGenerator.EXTERNAL_CRS)
        )

        polygon_expanded = place_gdf_buffer[0]

        self.G = ox.graph.graph_from_polygon(polygon_expanded, network_type=self.network_type)

        # impute speed on all edges missing data
        self.G = ox.add_edge_speeds(self.G)

        # calculate travel time (seconds) for all edges
        self.G = ox.add_edge_travel_times(self.G)

        self.G_projected = ox.project_graph(self.G, to_crs=self.internal_crs)

        self.county_gdf = place_gdf
        self.county_polygon = place_gdf["geometry"][0]

    def _plot_OSM(self):
        fig, ax = ox.plot_graph(self.G, show=False, close=False, edge_color="#999999", edge_alpha=0.2, node_size=0)
        self.county_gdf.plot(ax=ax, ec="none", alpha=0.6, zorder=-1)
        plt.show()

    def generate_isochrone(self, lat, lon, travel_time):
        # Generate an isochrone geometry object for the given location and travel_time using OSM data
        # https://github.com/gboeing/osmnx-examples/blob/main/notebooks/13-isolines-isochrones.ipynb

        ##### Coordinates not projected
        center_node = ox.distance.nearest_nodes(self.G, lon, lat)

        subgraph = nx.ego_graph(self.G, center_node, radius=travel_time * 60, distance="travel_time")

        node_points = [Point((data["x"], data["y"])) for node, data in subgraph.nodes(data=True)]
        nodes_gdf = gpd.GeoDataFrame({"id": list(subgraph.nodes)}, geometry=node_points)

        nodes_gdf = nodes_gdf.set_index("id")
        edge_lines = []
        for n_fr, n_to in subgraph.edges():
            f = nodes_gdf.loc[n_fr].geometry
            t = nodes_gdf.loc[n_to].geometry
            edge_lookup = self.G.get_edge_data(n_fr, n_to)[0].get("geometry", LineString([f, t]))
            edge_lines.append(edge_lookup)
        edge_gdf = gpd.GeoSeries(edge_lines)

        ############ projected data to calculate buffers
        # set to internal CRS so buffers can be calculated in meters
        nodes_gdf = nodes_gdf.set_crs(self.EXTERNAL_CRS).to_crs(self.internal_crs)
        edge_gdf = edge_gdf.set_crs(self.EXTERNAL_CRS).to_crs(self.internal_crs)

        n = nodes_gdf.buffer(self.isochrone_buffer_m).geometry
        e = edge_gdf.buffer(self.isochrone_buffer_m).geometry
        all_gs = list(n) + list(e)
        new_iso = gpd.GeoSeries(all_gs).set_crs(self.internal_crs)

        ######### Convert back to lat/lon coordinates for consistency
        new_iso = new_iso.to_crs(OsmIsochroneGenerator.EXTERNAL_CRS).union_all()

        return new_iso

    def isoplot(self, isochrone_polys: list):
        # make the isochrone polygons
        gdf = gpd.GeoDataFrame(geometry=isochrone_polys)

        # plot the network then add isochrones as colored polygon patches
        fig, ax = ox.plot_graph(self.G, show=False, close=False, edge_color="#999999", edge_alpha=0.2, node_size=0)
        gdf.plot(ax=ax, color="green", ec="none", alpha=0.6, zorder=-1)
        self.county_gdf.plot(ax=ax, ec="none", alpha=0.5, zorder=-1)
        plt.show()

    def get_isochrones(
        self, locations: pd.core.frame.DataFrame, lat_column: str, lon_column: str, travel_time: int = 5
    ):
        # https://stackoverflow.com/questions/67189283/how-to-keep-the-original-order-of-input-when-using-threadpoolexecutor
        # get an array of isochrone geometry objects for the given array of locations

        latitudes = locations[lat_column]
        longitudes = locations[lon_column]
        start = time.time()
        max_workers = min(4, os.cpu_count())
        coordinates = zip(latitudes, longitudes)
        processes = []
        isochrone_list = []
        counter = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, os.cpu_count())) as executor:
            for lat, lon in coordinates:
                processes.append(
                    executor.submit(self.get_isochrone, **{"lat": lat, "lon": lon, "travel_time": travel_time})
                )
            print("Jobs submitted")
            for index, task in enumerate(processes):
                result = task.result()
                if counter % 10 == 0:
                    print(f"Count: {counter}, Time Elapsed: {time.time()-start:.2f} seconds")
                counter += 1
                # print(result)
                isochrone_list.append(result)

        geometry = gpd.GeoSeries(isochrone_list, index=locations.index).set_crs(self.EXTERNAL_CRS)

        gdf = gpd.GeoDataFrame(locations, geometry=geometry)
        stop = time.time()
        print(
            f"Isochrone Collection Time Elapsed: {stop-start:.2f} seconds with {max_workers} thread workers, travel_time={travel_time} min"
        )

        return gdf

    def snap_to_road(self, origins, lat_column: str, lon_column: str):
        origins_gs = gpd.GeoSeries(
            gpd.points_from_xy(origins[lon_column], origins[lat_column]), index=origins.index, crs=self.EXTERNAL_CRS
        )
        ###################
        # working in projected space for distances
        origins_gs = origins_gs.to_crs(self.internal_crs)

        center_nodes, distances = ox.distance.nearest_nodes(
            self.G_projected, origins_gs.x, origins_gs.y, return_dist=True
        )

        # extract node data
        node_points = [
            Point((self.G_projected.nodes[node]["x"], self.G_projected.nodes[node]["y"])) for node in center_nodes
        ]
        nodes_gs = gpd.GeoSeries(node_points, index=origins.index, crs=self.internal_crs)

        #########
        # Return to lat/lon
        nodes_gs = nodes_gs.to_crs(self.EXTERNAL_CRS)
        origins_offset_gdf = gpd.GeoDataFrame(origins, geometry=nodes_gs, crs=self.EXTERNAL_CRS)
        origins_offset_gdf["offset_m"] = distances
        return origins_offset_gdf

    def check_coverage(self, origins_df, lat_column: str, lon_column: str, snap_to_road, isochrones_gdf, N):
        # Check whether all origins are covered by at least N isochrone geometries

        # for a gdf with columns for latitude and longitude, compare against a list of polygons in the isochrones gdf. count how many do not fall within at least N polygons

        # put together a GeoDataFrame that can be used to do a spatial join with isochrones
        if snap_to_road:
            origins_gdf = gpd.GeoDataFrame(
                origins_df,
                geometry=gpd.points_from_xy(origins_df[lon_column], origins_df[lat_column]),
                crs=self.EXTERNAL_CRS,
            )
        else:
            origins_gdf = self.snap_to_road(origins_df, lat_column=lat_column, lon_column=lon_column)

        gdf_check = origins_gdf.sjoin(isochrones_gdf, how="left", predicate="within")

        print(
            "Blocks in polling area radius",
            gdf_check.loc[:, ["id_orig", "dest_type"]].groupby("id_orig").count().value_counts(),
        )

        grouped_df = gdf_check.loc[:, ["id_orig", "dest_type"]].groupby("id_orig").count()
        count = len(grouped_df.query(f"`dest_type` < {N}"))

        if count > 0:
            raise CoverageError(uncovered_locations=count)

    def get_isochrone(self, lat, lon, travel_time: int):
        # Attempt to load the shapefile
        filename = f"{self.travel_method}_{lat:.4f}_{lon:.4f}_{travel_time}.shp"
        isochrone = self.load_shapefile(filename)

        # If the shapefile does not exist, generate and save the result
        if isochrone is None:
            isochrone = self.generate_isochrone(lat, lon, travel_time)
            self.save_shapefile(filename, isochrone)

        return isochrone


# this class should be initialized with a censusdata object and parameters for the isochrone generation. This may include travel method and a list of travel times

# this class will have a method which takes a location and a time to create an isochrone geometry object

# this class will have a method which takes an array of locations and makes an array of isochrone geometry objects

# this class will have a method to take and array of origins and an array of destinations and check whether all origins are covered by at least N isochrone geometries
