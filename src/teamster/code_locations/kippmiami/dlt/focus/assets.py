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
        # the memory keys leaves the shared step-pod block's cpu request and
        # limit in `.k8s/dagster/values-override.yaml` untouched. A SHALLOW
        # merge would replace `resources` wholesale and drop the cpu sizing
        # silently.
        #
        # The request matters as much as the limit. Under node memory pressure
        # the kubelet evicts the pod furthest over its request first, and an
        # evicted step pod hangs the run (its replacement exits on Dagster's
        # duplicate-start guard) instead of failing it. So the request sits
        # at the wide-tick peak, and the limit adds headroom so a rarer, wider
        # tick is not OOM-killed.
        #
        # Do not lower either against a sampled figure: GCP samples memory
        # every 60s and these pods live a couple of minutes, so any measured
        # peak is a floor. Peak scales with how many tables a tick selects (5
        # concurrent dlt extract workers, `FOCUS_CHUNK_SIZE` rows buffered
        # each). If this also runs short, the next lever is the
        # `dlt_extract_workers` run tag, not more memory.
        # Incident detail: tests/libraries/test_dlt_focus_memory_limit.py.
        op_tags={
            "dagster-k8s/config": {
                "container_config": {
                    "resources": {
                        "requests": {"memory": "3.0Gi"},
                        "limits": {"memory": "3.5Gi"},
                    }
                }
            }
        },
    )
]
