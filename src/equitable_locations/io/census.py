from censusdis import states
import censusdis.data as ced
import geopandas as gpd


class CensusData:
    DATASET = "dec/pl"
    YEAR = 2020

    P3_COLUMNS = {
        "GEO_ID": "GEO_ID",
        "NAME": "NAME",
        "P3_001N": "population",  # Total population
        "P3_003N": "white",  # White alone
        "P3_004N": "black",  # Black or African American alone
        "P3_005N": "native",  # American Indian or Alaska Native alone
        "P3_006N": "asian",  # Asian alone
        "P3_007N": "pacific_islander",  # Native Hawaiian and Other Pacific Islander alone
        "P3_008N": "other",  # Some other race alone
        "P3_009N": "multiple_races",  # Two or More Races
    }

    P4_COLUMNS = {
        "GEO_ID": "GEO_ID",
        "NAME": "NAME",
        "P4_001N": "population",  # Total population
        "P4_002N": "hispanic",  # Total hispanic
        "P4_003N": "non-hispanic",  # Total non-hispanic #TODO remove hyphen
    }

    BLOCK_SHAPE_COLS = {
        "GEOID20": "GEOID20",
        "INTPTLAT20": "orig_lat",
        "INTPTLON20": "orig_lon",
    }

    BLOCK_GROUP_SHAPE_COLS = {
        "GEOID20": "GEOID20",
        "INTPTLAT20": "orig_lat",
        "INTPTLON20": "orig_lon",
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
        self.county_code, self.county_name = self._get_county_code(county=county)

        self.block_data = self._get_block_data()

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
        variables = set(list(CensusData.P3_COLUMNS.keys()) + list(CensusData.P4_COLUMNS.keys()))

        df = ced.download(
            # First we specify the dataset and year:
            dataset=CensusData.DATASET,
            vintage=CensusData.YEAR,
            # Next, the group of variables we want to get data for:
            download_variables=variables,
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
            with_geometry=True,
        )

        return df

    # def get_data(self, county):
    #     data = self.read_cache(county)
    #     if data:
    #         return data
    #     else:
    #         data = self.fetch_data(county)
    #         self.cache_data(county, data)
    #         return data

    # def fetch_data(self, county):
    #     url = f"{self.base_url}?get=POP,NAME&for=county:{county}&in=state:*"
    #     response = requests.get(url)
    #     if response.status_code == 200:
    #         data = json.loads(response.text)
    #         return data
    #     else:
    #         raise Exception("Failed to fetch data from the API.")

    # def cache_data(self, county, data):
    #     cache = self.read_cache()
    #     cache[county] = data
    #     with open(self.cache_file, "w") as file:
    #         json.dump(cache, file)

    # def read_cache(self, county=None):
    #     try:
    #         with open(self.cache_file, "r") as file:
    #             cache = json.load(file)
    #             if county:
    #                 return cache.get(county)
    #             else:
    #                 return cache
    #     except FileNotFoundError:
    #         return None

