from equitable_locations.io.census import CensusData
from equitable_locations.io.locations import create_origins, create_destinations
from pathlib import Path
from equitable_locations.io.osm import OsmIsochroneGenerator
from equitable_locations.common.distance import DistanceGenerator
from equitable_locations.io.model_config import PollingModelConfig
from equitable_locations.common.model_data import clean_data, alpha_min
from equitable_locations.optimization.model_factory import polling_model_factory
from equitable_locations import PROJECT_ROOT, RESULT_ROOT, EQUITABLE_LOG_FOLDER, PARTNER_DATA_ROOT
from importlib import resources
from equitable_locations.optimization.model_results import (
    incorporate_result,
    demographic_domain_summary,
    demographic_summary,
    write_results,
)
from equitable_locations.optimization.model_penalties import incorporate_penalties
import pyomo.environ as pyo
import time
import datetime


def run_model(config: PollingModelConfig):
    if PARTNER_DATA_ROOT:
        partner_data = PARTNER_DATA_ROOT.joinpath(config.relative_partner_data_file_path)
    else:
        # use the config file parent location
        partner_data = config.config_file_path.parent.joinpath(config.relative_partner_data_file_path)

    if RESULT_ROOT:
        result_folder = RESULT_ROOT.joinpath(config.relative_result_folder)
    else:
        # use the config file parent location
        result_folder = config.config_file_path.parent.joinpath(config.relative_result_folder)
        if not result_folder.exists():
            result_folder.mkdir(parents=True)

    print(f"Loading partner data: {partner_data}")
    print(f"Results to {result_folder}")

    county_census_data = CensusData(state=config.state_name, county=config.county_name)

    df_origins = create_origins(county=county_census_data)
    df_destinations = create_destinations(county=county_census_data, partner_data=partner_data)

    county_isochrone_generator = OsmIsochroneGenerator(
        censusdata=county_census_data,
        travel_method="drive",
        isochrone_buffer_m=304.8,
    )

    # filter to location_type not in config.bad_types
    filtered_destinations = df_destinations.loc[~df_destinations.loc[:, "location_type"].isin(config.bad_types), :]

    travel_times = [5, 10, 15, 20, 25, 30]

    distance_gen = DistanceGenerator(
        isochrone_generator=county_isochrone_generator,
        times=travel_times,
        origins=df_origins,
        destinations=filtered_destinations,
        snap_origin=True,
        # use_minimum_time=True,
    )

    gdf_all = distance_gen.calc()

    # get main data frame
    dist_df = clean_data(gdf_all.copy(), config, False)

    # get alpha
    alpha_df = clean_data(gdf_all.copy(), config, True)
    alpha = alpha_min(alpha_df)

    # build model
    ea_model = polling_model_factory(dist_df, alpha, config)

    print("model preparation complete")

    LIMITS_GAP = 0.02
    LP_THREADS = 6

    solver = pyo.SolverFactory("appsi_highs")
    solver.options = {"limits/time": config.time_limit, "limits/gap": LIMITS_GAP, "lp/threads": LP_THREADS}

    log_file_path = EQUITABLE_LOG_FOLDER / "rotating-logfile.log"

    start = time.time()
    results = solver.solve(ea_model, tee=True)
    end = time.time()
    print(f"Elapsed: {end-start:.2f} seconds")

    run_prefix = f"{datetime.datetime.now().isoformat().replace(":","-")[0:16]}_"

    # incorporate result into main dataframe
    result_df = incorporate_result(dist_df, ea_model)

    # incorporate site penalties as appropriate
    result_df = incorporate_penalties(dist_df, alpha, run_prefix, result_df, ea_model, config, log_file_path)

    # calculate the new alpha given this assignment
    alpha_new = alpha_min(result_df)

    # calculate the average distances traveled by each demographic to the assigned precinct
    demographic_prec = demographic_domain_summary(result_df, "id_dest")

    # calculate the average distances traveled by each demographic by residence
    demographic_res = demographic_domain_summary(result_df, "id_orig")

    # calculate the average distances (and y_ede if beta !=0) traveled by each demographic
    demographic_ede = demographic_summary(demographic_res, result_df, config.beta, alpha_new)

    write_results(
        result_folder,
        run_prefix,
        result_df,
        demographic_prec,
        demographic_res,
        demographic_ede,
    )
