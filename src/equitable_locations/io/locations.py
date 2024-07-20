import pandas as pd
from equitable_locations.io.census import CensusData
from pathlib import Path

DESTINATION_FINAL_COLS = {
    "id_dest": "string",
    "address": "string",
    "location_type": "string",
    "dest_type": "category",
    "dest_lat": "float64",
    "dest_lon": "float64",
}


def create_origins(county: CensusData) -> pd.DataFrame:
    blocks = county.block_data.copy()

    blocks.loc[:, "county"] = pd.Series([county.county_name] * len(blocks), dtype="category")

    origin_columns = [
        "id_orig",
        "orig_lat",
        "orig_lon",
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
        "county",
    ]

    return blocks.loc[:, origin_columns]


def create_destinations(county: CensusData, partner_data: Path) -> pd.DataFrame:
    df_partner_data = partner_data_destinations(partner_data)
    df_block_groups = block_group_destinations(county)

    col = "dest_type"
    all_dest_type = df_partner_data[col].cat.categories.union(df_block_groups[col].cat.categories)
    df_partner_data[col] = df_partner_data[col].cat.set_categories(all_dest_type)
    df_block_groups[col] = df_block_groups[col].cat.set_categories(all_dest_type)

    pd.concat([df_partner_data, df_block_groups]).dtypes

    return pd.concat([df_partner_data, df_block_groups])


def partner_data_destinations(partner_data: Path) -> pd.DataFrame:
    location_cols = {
        "Location": "id_dest",
        "Address": "address",
        "Location type": "location_type",
    }

    df_locations = pd.read_csv(partner_data, dtype="string")

    df_locations.rename(columns=location_cols, inplace=True)

    # change the lat, long into two columns
    df_locations[["dest_lat", "dest_lon"]] = (
        df_locations["Lat, Long"].str.split(pat=", ", expand=True).apply(pd.to_numeric)
    )
    df_locations.drop(["Lat, Long"], axis=1, inplace=True)

    # TODO: Change dest type to a categorical column on input data
    df_locations.loc[:, "dest_type"] = "polling"
    df_locations.loc[df_locations.loc[:, "location_type"].str.contains("Potential"), "dest_type"] = "potential"

    #     column_dtypes = {
    #     key: val
    #     for key, val in {**CensusData.DATA_COLUMNS_FORMAT, **CensusData.BLOCK_SHAPE_COLS_FORMAT}.items()
    #     if key in gdf_data.columns
    # }

    # return gdf_data.astype(dtype=column_dtypes)

    return df_locations.loc[:, DESTINATION_FINAL_COLS.keys()].astype(dtype=DESTINATION_FINAL_COLS)


def block_group_destinations(county: CensusData) -> pd.DataFrame:
    # extract as a copy to avoid modifying source data
    block_group_destinations = county.block_group_data.loc[:, ["id_dest", "dest_lat", "dest_lon"]].copy()

    # add columns with values indicating block group source
    block_group_destinations.loc[:, "address"] = None
    block_group_destinations.loc[:, "location_type"] = "bg_centroid"
    block_group_destinations.loc[:, "dest_type"] = "bg_centroid"

    return block_group_destinations.loc[:, DESTINATION_FINAL_COLS.keys()].astype(dtype=DESTINATION_FINAL_COLS)
