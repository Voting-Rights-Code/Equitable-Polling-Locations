import time
from typing import Union
import geopandas as gpd
from geopandas.geodataframe import GeoDataFrame
import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString, Point, Polygon
import concurrent.futures
import os
from epl_io.isochrone import CoverageError, BaseIsochroneGenerator
from epl_io.direct import BaseDistanceCalculator
from model_config import OsmArgs


def get_osm_data(
    place: dict, network_type: str, buffer_m: Union[float, int]
) -> tuple[GeoDataFrame, nx.classes.multidigraph.MultiDiGraph]:
    # Geocode the place to get the geometry
    place_gdf = ox.geocode_to_gdf(place)

    # identify and store the crs to use for the county
    # this will be used for internal calculations for all buffers
    internal_crs = place_gdf.estimate_utm_crs()

    place_gdf_buffer = (
        place_gdf.to_crs(internal_crs)
        .buffer(buffer_m, cap_style="round", join_style="round")
        .to_crs(OsmIsochroneGenerator.EXTERNAL_CRS)
    )

    polygon_expanded = place_gdf_buffer[0]

    G = ox.graph.graph_from_polygon(polygon_expanded, network_type=network_type)

    # impute speed on all edges missing data
    G = ox.add_edge_speeds(G)

    # calculate travel time (seconds) for all edges
    G = ox.add_edge_travel_times(G)

    internal_crs = place_gdf.estimate_utm_crs()
    G_projected = ox.project_graph(G, to_crs=internal_crs)

    return place_gdf, G, internal_crs, G_projected


# create an OSM isochrone generator class inheriting from the base isochrone generator class
class OsmIsochroneGenerator(BaseIsochroneGenerator):
    def __init__(self, state_name, county_name, osm_args: OsmArgs):
        super().__init__()
        self.travel_method = osm_args.network_type

        # update base folder for isochrone data by state and county
        state_folder = state_name.replace(" ", "_")
        county_folder = county_name.replace(" ", "_")
        self.isochrone_dir = self.isochrone_dir / state_folder / county_folder
        self.isochrone_dir.mkdir(parents=True, exist_ok=True)

        self.place = {"county": county_name, "state": state_name}
        self.network_type = osm_args.network_type
        self.isochrone_buffer_m = osm_args.isochrone_buffer_m

        self.load_osm_data(osm_args.county_buffer_m)

    def load_osm_data(self, buffer_m):
        # Get a shapefile of the county specified by self.place. expand the shapefile with a radius of 5 miles.

        (self.county_gdf, self.G, self.internal_crs, self.G_projected) = get_osm_data(
            place=self.place, network_type=self.network_type, buffer_m=buffer_m
        )

        self.county_polygon = self.county_gdf["geometry"][0]

    def _plot_OSM(self):
        fig, ax = ox.plot_graph(self.G, show=False, close=False, edge_color="#999999", edge_alpha=0.2, node_size=0)
        self.county_gdf.plot(ax=ax, ec="none", alpha=0.6, zorder=-1)
        plt.show()

    def generate_isochrone(self, lat, lon, travel_time) -> Polygon:
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
        coordinates = zip(latitudes, longitudes, strict=False)
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

        # for a gdf with columns for latitude and longitude, compare against a list of polygons in the isochrones gdf.
        # count how many do not fall within at least N polygons

        # put together a GeoDataFrame that can be used to do a spatial join with isochrones
        if snap_to_road:
            origins_gdf = self.snap_to_road(origins_df, lat_column=lat_column, lon_column=lon_column)
        else:
            origins_gdf = gpd.GeoDataFrame(
                origins_df,
                geometry=gpd.points_from_xy(origins_df[lon_column], origins_df[lat_column]),
                crs=self.EXTERNAL_CRS,
            )

        gdf_check = origins_gdf.sjoin(isochrones_gdf, how="left", predicate="within")

        print(
            "Blocks in polling area radius\n",
            pd.DataFrame(
                gdf_check.loc[:, ["id_orig", "dest_type"]]
                .groupby("id_orig")
                .count()
                .value_counts(sort=True, ascending=True)
            )
            .reset_index()
            .rename({"dest_type": "DestinationsPerOrigin", "count": "NumberOfOrigins"}, axis=1),
        )

        grouped_df = gdf_check.loc[:, ["id_orig", "dest_type"]].groupby("id_orig").count()
        count = len(grouped_df.query(f"`dest_type` < {N}"))

        if count > 0:
            raise CoverageError(uncovered_locations=count)

        return True


class OsmDistanceCalculator(BaseDistanceCalculator):
    def __init__(self, state_name, county_name, osm_args: OsmArgs, time_units: bool):
        super().__init__()

        # update base folder for isochrone data by state and county
        state_folder = state_name.replace(" ", "_")
        county_folder = county_name.replace(" ", "_")
        self.distance_dir = self.distance_dir / state_folder / county_folder
        self.distance_dir.mkdir(parents=True, exist_ok=True)

        # TODO: local database integration for caching
        # self.database_path = self.distance_dir / "default.db"

        # load data for county
        self.place = {"county": county_name, "state": state_name}
        self.network_type = osm_args.network_type
        self.load_osm_data(osm_args.county_buffer_m)

        # specify distance vs time
        self.time_units = time_units

    def load_osm_data(self, buffer_m):
        (self.county_gdf, self.G, self.internal_crs, self.G_projected) = get_osm_data(
            place=self.place, network_type=self.network_type, buffer_m=buffer_m
        )

    def calc(self, origin_latlon: tuple[float, float], destination_latlon: tuple[float, float]):
        # use specified graph to go and determine the route, return distance

        num_cpus = os.cpu_count()
        if num_cpus:
            num_cpus = num_cpus // 4
        else:
            num_cpus = 1

        # create a series with the origin and destination. x values are longitude
        points_gs = gpd.GeoSeries(
            gpd.points_from_xy(
                x=[origin_latlon[1], destination_latlon[1]], y=[origin_latlon[0], destination_latlon[0]]
            ),
            crs=self.EXTERNAL_CRS,
        )
        ###################
        # working in projected space for distances
        points_gs = points_gs.to_crs(self.internal_crs)

        # find nodes, save snap-to-node distance for part of travel distance.
        nodes, distances = ox.distance.nearest_nodes(self.G_projected, points_gs.x, points_gs.y, return_dist=True)

        origin_node = nodes[0]
        destination_node = nodes[1]

        if self.time_units:
            # Assume 15mph before on-road distance.
            # time =distance/velocity
            #             1 hr      1 mi      3600 s    distance m
            # time (s) = ------- x ------- x ------- x ------------
            #             15 mi    1609 m      1 hr        1
            extra_distance_mph = 15
            constant = 1 / extra_distance_mph * 3600 / 1609.344
            extra_distances = [x * constant for x in distances]
            weight = "travel_time"
        else:
            extra_distances = distances
            weight = "length"

        shortest_path = ox.routing.shortest_path(
            G=self.G_projected, orig=origin_node, dest=destination_node, weight=weight, cpus=num_cpus
        )

        # See https://github.com/gboeing/osmnx-examples/blob/main/notebooks/02-routing-speed-time.ipynb
        distance = int(sum(ox.routing.route_to_gdf(G=self.G_projected, route=shortest_path, weight=weight)[weight]))

        total_distance = sum([distance] + extra_distances)

        if self.time_units:
            # Convert to minutes
            return total_distance / 60
        else:
            return total_distance
