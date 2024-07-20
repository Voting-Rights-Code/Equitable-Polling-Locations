from censusdis import states
import censusdis.data as ced
import censusdis.values as cev
import geopandas as gpd
import pandas as pd
from pygris import blocks, block_groups


class CensusData:
    DATASET = "dec/pl"
    YEAR = 2020

    DATA_COLUMNS = {
        "GEO_ID": "GEO_ID",
        # "NAME": "NAME",
        "P3_001N": "population",  # Total population
        "P3_003N": "white",  # White alone
        "P3_004N": "black",  # Black or African American alone
        "P3_005N": "native",  # American Indian or Alaska Native alone
        "P3_006N": "asian",  # Asian alone
        "P3_007N": "pacific_islander",  # Native Hawaiian and Other Pacific Islander alone
        "P3_008N": "other",  # Some other race alone
        "P3_009N": "multiple_races",  # Two or More Races
        "P4_002N": "hispanic",  # Total hispanic
        "P4_003N": "non-hispanic",  # Total non-hispanic #TODO remove hyphen
    }

    DATA_COLUMNS_FORMAT = {
        "GEO_ID": "string",
        "NAME": "string",
        "population": "int64",  # Total population
        "white": "int64",  # White alone
        "black": "int64",  # Black or African American alone
        "native": "int64",  # American Indian or Alaska Native alone
        "asian": "int64",  # Asian alone
        "pacific_islander": "int64",  # Native Hawaiian and Other Pacific Islander alone
        "other": "int64",  # Some other race alone
        "multiple_races": "int64",  # Two or More Races
        "hispanic": "int64",  # Total hispanic
        "non-hispanic": "int64",  # Total non-hispanic #TODO remove hyphen
    }

    BLOCK_SHAPE_COLS = {
        "GEOID20": "id_orig",
        "INTPTLAT20": "orig_lat",
        "INTPTLON20": "orig_lon",
        "geometry": "geometry",
    }

    BLOCK_SHAPE_COLS_FORMAT = {
        "id_orig": "string",
        "orig_lat": "float64",
        "orig_lon": "float64",
        "geometry": "geometry",
    }

    BLOCK_GROUP_SHAPE_COLS = {
        "GEOID": "id_dest",
        "INTPTLAT": "dest_lat",
        "INTPTLON": "dest_lon",
        "geometry": "geometry",
    }

    BLOCK_GROUP_SHAPE_COLS_FORMAT = {
        "id_dest": "string",
        "dest_lat": "float64",
        "dest_lon": "float64",
        "geometry": "geometry",
    }

    def __init__(self, state: str, county: str, api_key=None):
        self.api_key = api_key
        if len(state) == 2:
            # Takes state codes like NJ
            self.state_code = states.IDS_FROM_ABBREVIATIONS[state]
        else:
            # Takes state names like New Jersey
            self.state_code = states.IDS_FROM_NAMES[state]

        self.state_name = states.NAMES_FROM_IDS[self.state_code]
        self.state_abbreviation = states.ABBREVIATIONS_FROM_IDS[self.state_code]
        self.county_code, self.county_name = self._get_county_code(county=county)

        self.block_data = self._get_block_data()
        self.block_group_data = self._get_block_group_data()

        # self.cache_file = "census_cache.json"

    def _get_county_code(self, county: str) -> tuple[str, str]:
        # lookup county codes
        # TODO cache/pull from cache
        df_counties = ced.download(
            dataset="acs/acs5",
            vintage=CensusData.YEAR,
            download_variables=["NAME"],
            state=self.state_code,
            county="*",
            api_key=self.api_key,
        )
        county_code = df_counties.loc[df_counties["NAME"].str.contains(county), ["COUNTY", "NAME"]]
        if len(county_code) > 1:
            raise ValueError("County name search for {} returned more than one result")
        elif len(county_code) == 0:
            raise ValueError("County name search for {} returned no results")

        code = county_code.iloc[0, 0]
        name = county_code.iloc[0, 1].split(" County,")[0]

        return code, name

    def _get_block_data(self) -> gpd.GeoDataFrame:
        # TODO: Update with new version. See https://github.com/censusdis/censusdis/issues/295
        df = ced.download(
            # First we specify the dataset and year:
            dataset=CensusData.DATASET,
            vintage=CensusData.YEAR,
            # Next, the group of variables we want to get data for:
            download_variables=CensusData.DATA_COLUMNS,
            # Next come filters that constrain what data we
            # want to load, specified as keyword arguments.
            # The narrowest of these, which in our case is
            # block, specifies the level of aggregation. We
            # use block=* to indicate all blocks within the
            # tracts we have specified.
            state=self.state_code,
            county=self.county_code,
            tract="*",
            block="*",
            # Finally, we put in our API key:
            api_key=self.api_key,
            set_to_nan=cev.ALL_SPECIAL_VALUES,
            with_geometry=False,
            # with_geometry_columns=True,
        )

        # use pygris to load geometry with latitude
        df_tiger = blocks(state=self.state_code, county=self.county_code, year=CensusData.YEAR, cache=True)
        # filter to only needed columns
        df_tiger = df_tiger.loc[:, CensusData.BLOCK_SHAPE_COLS.keys()]

        # reformat the geoid to match the tiger format and merge
        df.loc[:, "GEO_ID"] = df.loc[:, "GEO_ID"].str[-15:]
        gdf_data = df.merge(df_tiger, how="left", left_on="GEO_ID", right_on="GEOID20")

        # downselect columns
        selected_columns = list(CensusData.DATA_COLUMNS.keys()) + list(CensusData.BLOCK_SHAPE_COLS.keys())
        gdf_data = gdf_data.loc[:, selected_columns]
        gdf_data.drop("GEO_ID", axis=1, inplace=True)

        # Rename columns
        gdf_data = gdf_data.rename(columns=CensusData.DATA_COLUMNS)
        gdf_data = gdf_data.rename(columns=CensusData.BLOCK_SHAPE_COLS)

        # find set of columns to use for renaming
        column_dtypes = {
            key: val
            for key, val in {**CensusData.DATA_COLUMNS_FORMAT, **CensusData.BLOCK_SHAPE_COLS_FORMAT}.items()
            if key in gdf_data.columns
        }

        return gdf_data.astype(dtype=column_dtypes)

    def _get_block_group_data(self) -> gpd.GeoDataFrame:
        # TODO: Update with new version. See https://github.com/censusdis/censusdis/issues/295
        df = ced.download(
            # First we specify the dataset and year:
            dataset=CensusData.DATASET,
            vintage=CensusData.YEAR,
            # Next, the group of variables we want to get data for:
            download_variables=CensusData.DATA_COLUMNS,
            # Next come filters that constrain what data we
            # want to load, specified as keyword arguments.
            # The narrowest of these, which in our case is
            # block, specifies the level of aggregation. We
            # use block=* to indicate all blocks within the
            # tracts we have specified.
            state=self.state_code,
            county=self.county_code,
            tract="*",
            block_group="*",
            # Finally, we put in our API key:
            api_key=self.api_key,
            set_to_nan=cev.ALL_SPECIAL_VALUES,
            with_geometry=False,
            # with_geometry_columns=True,
        )

        # reformat the geoid to match the tiger format for merging (drop geo_id_prefix)
        df.loc[:, "GEO_ID"] = df.loc[:, "GEO_ID"].str[-12:]

        # use pygris to load geometry with latitude
        df_tiger = block_groups(state=self.state_code, county=self.county_code, year=CensusData.YEAR, cache=True)
        # filter to only needed columns
        df_tiger = df_tiger.loc[:, CensusData.BLOCK_GROUP_SHAPE_COLS.keys()]

        gdf_data = df.merge(df_tiger, how="left", left_on="GEO_ID", right_on="GEOID")

        # downselect columns
        selected_columns = list(CensusData.DATA_COLUMNS.keys()) + list(CensusData.BLOCK_GROUP_SHAPE_COLS.keys())
        gdf_data = gdf_data.loc[:, selected_columns]
        gdf_data.drop("GEO_ID", axis=1, inplace=True)

        # Rename columns
        gdf_data = gdf_data.rename(columns=CensusData.DATA_COLUMNS)
        gdf_data = gdf_data.rename(columns=CensusData.BLOCK_GROUP_SHAPE_COLS)

        # find set of columns to use for renaming
        column_dtypes = {
            key: val
            for key, val in {**CensusData.DATA_COLUMNS_FORMAT, **CensusData.BLOCK_GROUP_SHAPE_COLS_FORMAT}.items()
            if key in gdf_data.columns
        }

        return gdf_data.astype(dtype=column_dtypes)
