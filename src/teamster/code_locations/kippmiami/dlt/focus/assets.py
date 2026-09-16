import pathlib

import yaml
from dlt.common.configuration import resolve_configuration
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"

sql_database_credentials = resolve_configuration(
    ConnectionStringCredentials(), sections=("FOCUS_DB",)
)

config_assets = yaml.safe_load(config_file.read_text())["assets"]

tables = [
    # a["cursor_column"], not .get(): a new table added without a declared
    # cursor must fail loudly at module load, not silently become count-only.
    ProbeTable(name=a["table_name"], cursor_column=a["cursor_column"])
    for a in config_assets
]

"""Module-level so sensors.py can import it instead of re-parsing the YAML.

Keeps the credential resolution and config parse to one copy per code-location
import — both `assets.py` and `sensors.py` load unconditionally via
`dlt/focus/__init__.py`.
"""

assets = [
    build_focus_dlt_assets(
        sql_database_credentials=sql_database_credentials,
        code_location=CODE_LOCATION,
        tables=tables,
        # Memory only: `K8sConfigMergeBehavior` defaults to DEEP, so naming just
        # `limits.memory` leaves the shared step-pod block's `limits.cpu`
        # (1750m) and both requests in `.k8s/dagster/values-override.yaml`
        # untouched. A SHALLOW merge would replace `resources` wholesale and
        # drop the cpu sizing silently.
        #
        # Do not lower this against a sampled figure. The alert behind it caught
        # 92.6% of the old 2.5Gi limit, but GCP samples memory every 60s and
        # these pods live ~110s, so any measured peak is a floor. Peak scales
        # with how many tables a tick selects (5 concurrent dlt extract workers,
        # `FOCUS_CHUNK_SIZE` rows buffered each). If 3.0Gi also runs short, the
        # next lever is the `dlt_extract_workers` run tag, not more memory.
        # Incident detail: tests/libraries/test_dlt_focus_memory_limit.py.
        op_tags={
            "dagster-k8s/config": {
                "container_config": {"resources": {"limits": {"memory": "3.0Gi"}}}
            }
        },
    )
]
