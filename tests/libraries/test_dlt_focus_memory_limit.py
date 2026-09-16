"""Pins the Focus dlt op's memory limit and the merge that makes it safe.

`kippmiami__dlt__focus` reached 92.6% of the shared 2.5Gi step-pod limit
(~2.31 GiB) on 2026-09-16 and again the day before, both on 8-table sensor
ticks, which is what the per-asset 3.0Gi override in
`code_locations/kippmiami/dlt/focus/assets.py` answers. Two silent regressions
are possible and neither raises on its own, so both are pinned here:

1. The override is dropped or retyped in the code location -> the op silently
   returns to 2.5Gi and the next wide tick OOM-kills.
2. `dagster_k8s` stops defaulting to `K8sConfigMergeBehavior.DEEP` -> naming
   only `limits.memory` would replace the whole `resources` dict and silently
   drop the 1750m cpu limit from `.k8s/dagster/values-override.yaml`.

The code location is read with `ast`, not imported: it resolves `FOCUS_DB`
credentials eagerly at module scope and those are unset even under pytest (see
src/teamster/CLAUDE.md), so no import of it can succeed here.
"""

import ast
import json
import pathlib
from typing import Any

from dagster_k8s.container_context import K8sContainerContext
from dagster_k8s.job import K8sConfigMergeBehavior, UserDefinedDagsterK8sConfig
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable

CREDENTIALS = ConnectionStringCredentials("postgresql+psycopg://localhost:5432/db")

K8S_CONFIG_KEY = "dagster-k8s/config"
EXPECTED_MEMORY_LIMIT = "3.0Gi"

CODE_LOCATION_ASSETS = (
    pathlib.Path(__file__).parents[2]
    / "src/teamster/code_locations/kippmiami/dlt/focus/assets.py"
)

# The shared step-pod block in .k8s/dagster/values-override.yaml.
HELM_STEP_POD_RESOURCES = {
    "requests": {"cpu": "500m", "memory": "2.0Gi"},
    "limits": {"cpu": "1750m", "memory": "2.5Gi"},
}


def _code_location_op_tags() -> dict[str, Any]:
    """The `op_tags` literal passed to `build_focus_dlt_assets` in kippmiami."""
    tree = ast.parse(CODE_LOCATION_ASSETS.read_text())

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "build_focus_dlt_assets"):
            continue

        for keyword in node.keywords:
            if keyword.arg == "op_tags":
                return ast.literal_eval(keyword.value)

    raise AssertionError(
        "no build_focus_dlt_assets(op_tags=...) call found in"
        f" {CODE_LOCATION_ASSETS} -- the memory override was removed or renamed"
    )


def test_code_location_pins_the_memory_limit() -> None:
    resources = _code_location_op_tags()[K8S_CONFIG_KEY]["container_config"][
        "resources"
    ]

    assert resources["limits"]["memory"] == EXPECTED_MEMORY_LIMIT

    # Memory only, on purpose: anything else here relies on the deep merge
    # leaving the Helm cpu sizing alone, which the next test is what guards.
    assert "cpu" not in resources["limits"]
    assert "requests" not in resources


def test_op_tags_reach_the_op() -> None:
    """The factory must forward op_tags, or the override never reaches the pod."""
    assets = build_focus_dlt_assets(
        sql_database_credentials=CREDENTIALS,
        code_location="kippmiami",
        tables=[ProbeTable(name="discipline_referrals", cursor_column="updated_at")],
        op_tags=_code_location_op_tags(),
    )

    # Dagster serializes the k8s config to a JSON string on the op, not a dict.
    k8s_config = json.loads(assets.op.tags[K8S_CONFIG_KEY])

    assert (
        k8s_config["container_config"]["resources"]["limits"]["memory"]
        == EXPECTED_MEMORY_LIMIT
    )


def test_memory_only_override_preserves_the_helm_cpu_limit() -> None:
    """A memory-only override must not wipe the rest of `resources`.

    Guards the DEEP default: under SHALLOW, `resources` is replaced wholesale and
    the step pod silently loses its 1750m cpu limit and both requests.
    """
    override = UserDefinedDagsterK8sConfig.from_dict(
        _code_location_op_tags()[K8S_CONFIG_KEY]
    )

    assert override.merge_behavior == K8sConfigMergeBehavior.DEEP

    merged = K8sContainerContext._merge_k8s_config(
        UserDefinedDagsterK8sConfig(
            container_config={"resources": HELM_STEP_POD_RESOURCES}
        ),
        override,
    )
    resources = merged.container_config["resources"]

    assert resources == {
        "requests": {"cpu": "500m", "memory": "2.0Gi"},
        "limits": {"cpu": "1750m", "memory": EXPECTED_MEMORY_LIMIT},
    }
