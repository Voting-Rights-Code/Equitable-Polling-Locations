from typing import List
from pydantic import BaseModel, Field
import yaml
from equitable_locations import PROJECT_ROOT
from pathlib import Path
import enum

from equitable_locations.io.osm import OsmIsochroneGenerator
from pathlib import Path


class IsochroneType(enum.Enum):
    Osm = OsmIsochroneGenerator


class PollingModelConfig(BaseModel):
    """A simple config class to run models."""

    state_name: str
    """Name of the state of interest"""
    county_name: str
    """Name of the county of interest"""
    year: List[str]
    """list of years to be studied"""
    bad_types: List[str]
    """list of location types not to be considered in this model"""
    beta: float
    """level of inequality aversion: [-10,0], where 0 indicates indifference, and thus uses the
    mean. -2 isa good number """
    time_limit: int
    """How long the solver should try to find a solution"""
    penalized_sites: List[str] = Field(default_factory=list)
    """A list of locations for which the preference is to only place a polling location there
    if absolutely necessary for coverage, e.g. fire stations."""

    precincts_open: int = None
    """The total number of precincts to be used this year. If no
    user input is given, this is calculated to be the number of
    polling places identified in the data."""
    maxpctnew: float = 1.0
    """The percent on new polling places (not already defined as a
    polling location) permitted in the data. Default = 1. I.e. can replace all existing locations"""
    minpctold: float = 0
    """The minimun number of polling places (those already defined as a
    polling location) permitted in the data. Default = 0. I.e. can replace all existing locations"""
    max_min_mult: float = 1.0
    """A multiplicative factor for the min_max distance caluclated
    from the data. Should be >= 1. Default = 1."""
    capacity: float = 1.0
    """A multiplicative factor for calculating the capacity constraint. Should be >= 1.
    Default = 1."""
    relative_result_folder: str = "results"
    """ The location to write out results """

    config_file_path: Path = None
    """ The path to the file that defines this config.  """

    relative_partner_data_file_path: str
    """ The path to the file that defines partner data.  """

    def __post_init__(self):
        if not self.result_folder:
            state_folder = self.state_name.replace(" ", "_")
            county_folder = self.county_name.replace(" ", "_")

            self.result_folder = PROJECT_ROOT / "untracked" / "results" / state_folder / county_folder

    @staticmethod
    def load_config_file(config_path: Path) -> "PollingModelConfig":
        """Return an instance of RunConfig from a yaml file."""
        with open(config_path, "r", encoding="utf-8") as yaml_file:
            config = yaml.safe_load(yaml_file)

        config["config_file_path"] = config_path

        return PollingModelConfig.load_config(config)

    @staticmethod
    def load_config(config: dict) -> "PollingModelConfig":
        """Return an instance of RunConfig from a yaml file."""
        # test for location to enable backwards compatibility
        if config.get("location"):
            state_name = config["location"].split("_")[1]
            county_name = config["location"].split("_")[0]
            config["state_name"] = state_name
            config["county_name"] = county_name

            config.pop("location", None)

        # safely coerce values into correct type
        if config.get("partner_data_file_path"):
            config["partner_data_file_path"] = Path(config["partner_data_file_path"])

        result = PollingModelConfig(**config)
        return result


def load_configs(config_paths: List[Path]) -> List[PollingModelConfig]:
    """Look through the list of files and confim they exist on disk, print any missing files or errors."""
    results: List[PollingModelConfig] = []

    for config_path in config_paths:
        config = PollingModelConfig.load_config(config_path)
        results.append(config)

    return results
