"""
This analyses the configs in order to determin the liquidity of the vaults
We want to make sure that the vaults are liquid enough to be able to be able to be used.
"""

CONFIG_DIR = "configs/generated"

import os
import json
import pandas as pd
import yaml
