import json
import pathlib

from .. import CODE_LOCATION

dbt_manifest = json.loads(
    s=pathlib.Path(f"src/dbt/{CODE_LOCATION}/target/manifest.json").read_text()
)
