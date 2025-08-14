''' A simple dataclass to contain the nessicary variables to execute a model run '''

from dataclasses import dataclass

import pandas as pd

from .model_config import PollingModelConfig
from .model_factory import PollingModel

@dataclass
class RunSetup:
    polling_locations_set_id: str
    locations_df: pd.DataFrame
    dist_df: pd.DataFrame
    alpha: float
    alpha_df: pd.DataFrame
    ea_model: PollingModel
    run_prefix: str
    config: PollingModelConfig

