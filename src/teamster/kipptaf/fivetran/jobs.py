import pathlib

import yaml

from teamster.core.fivetran.jobs import build_fivetran_start_sync_job
from teamster.kipptaf import CODE_LOCATION

config_path = pathlib.Path(__file__).parent / "config"

__all__ = []

for config_file in config_path.glob("*.yaml"):
    config = yaml.safe_load(config_file.read_text())

    __all__.append(
        build_fivetran_start_sync_job(
            code_location=CODE_LOCATION,
            connector_id=config["connector_id"],
            connector_name=config["connector_name"],
        )
    )
