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
        # Memory only. The shared step-pod block in `.k8s/dagster/
        # values-override.yaml` gives 2.0Gi requests / 2.5Gi limits, and this op
        # reached 92.6% of that limit (~2.31 GiB) on 2026-09-16 and again the
        # day before, both on 8-table sensor ticks. 3.0Gi is ~20% over the
        # observed peak — the same headroom rule that block's cpu limit uses.
        #
        # Treat 2.31 GiB as a FLOOR on the true peak, not the peak: the metric
        # samples every 60s and these pods live ~110s, so most runs of this op
        # are never sampled at all. Peak scales with how many tables a tick
        # selects, since each of dlt's 5 default extract workers holds a
        # 50k-row pyarrow chunk (`FOCUS_CHUNK_SIZE`) — a tick that drifts more
        # large tables at once goes higher. If 3.0Gi is ever not enough, the
        # other lever is capping concurrency via the `dlt_extract_workers` run
        # tag rather than buying more memory again.
        #
        # `K8sConfigMergeBehavior` defaults to DEEP, so naming only
        # `limits.memory` here leaves that block's `limits.cpu` (1750m) and both
        # requests untouched. A SHALLOW merge would replace the whole
        # `resources` dict and silently drop the cpu sizing.
        op_tags={
            "dagster-k8s/config": {
                "container_config": {"resources": {"limits": {"memory": "3.0Gi"}}}
            }
        },
    )
]
