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
        # `K8sConfigMergeBehavior` defaults to DEEP, so the cpu limit in the
        # shared step-pod block of `.k8s/dagster/values-override.yaml` survives
        # this override. A SHALLOW merge would replace `resources` wholesale
        # and drop it silently.
        #
        # The memory request matters as much as the limit. Under node memory
        # pressure the kubelet evicts the pod furthest over its request first.
        # Going over the limit is no better: the OOM kill spends the Job's one
        # retry, and that replacement pod also exits on Dagster's
        # duplicate-start guard. Either way the run hangs until the sensor's
        # `dagster/max_runtime`, so the request sits above the widest observed
        # tick and the limit adds headroom above that.
        #
        # The cpu request follows the memory request: Scale-Out requires an
        # exact 1:4 cpu:memory request ratio and Autopilot raises the smaller
        # resource to fit, so it is written out rather than left implicit.
        #
        # Do not lower the memory figures against a sampled figure: GCP samples
        # memory every 60s and these pods live a few minutes, so any measured
        # peak is a floor. Peak scales with how many tables a tick selects (5
        # concurrent dlt extract workers, `FOCUS_CHUNK_SIZE` rows buffered
        # each). If this also runs short, the next lever is the
        # `dlt_extract_workers` run tag, not more memory.
        op_tags={
            "dagster-k8s/config": {
                "container_config": {
                    "resources": {
                        "requests": {"cpu": "750m", "memory": "3.0Gi"},
                        "limits": {"memory": "3.5Gi"},
                    }
                }
            }
        },
    )
]
