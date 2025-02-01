from dataclasses import dataclass
from typing import Dict, Optional, List
from datetime import datetime
import re

import pandas as pd

import sqlalchemy
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker as SessionMaker

import sqlalchemy_main
import models as Models
from utils import generate_uuid

from google.oauth2.service_account import Credentials
from google.cloud import bigquery

import utils

inspector = inspect(Models.ModelConfig)
columns = [column.name for column in inspector.columns]
breakpoint()
print(inpsector)