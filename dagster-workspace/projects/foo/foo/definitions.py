from pathlib import Path

import foo.defs
from dagster_components import load_defs

defs = load_defs(defs_root=foo.defs)
