"""Performance benchmarks for automation condition evaluation strategies.

Compares evaluation time across three strategies for assigning automation
conditions to kipptaf dbt assets:

1. **Baseline**: All views get dbt_view_automation_condition() (no special
   union_relations handling). This was the state before PR #3440.
2. **Union-relations only** (current): Views with union_relations in raw_code
   get dbt_union_relations_automation_condition(); other views get the plain
   view condition.
3. **All views**: Every view gets _build_any_ancestor_code_version_changed()
   added to its condition, not just union_relations views.

Run with: uv run pytest tests/test_automation_condition_performance.py -s
"""

import json
import signal
import time
from contextlib import contextmanager

import pytest
from dagster import (
    AssetKey,
    AssetSpec,
    DagsterInstance,
    Definitions,
    evaluate_automation_conditions,
)

from teamster.core.automation_conditions import (
    _build_any_ancestor_code_version_changed,
    _build_dbt_condition,
    dbt_table_automation_condition,
    dbt_union_relations_automation_condition,
    dbt_view_automation_condition,
)

_SENSOR_BUDGET_SECONDS = 30
_EVALUATION_TIMEOUT_SECONDS = 120

_VIEW_TAG = {"dagster/materialized": "view"}
_TABLE_TAG = {"dagster/materialized": "table"}

# Pre-build conditions once (they're pure data structures)
_VIEW_CONDITION = dbt_view_automation_condition()
_TABLE_CONDITION = dbt_table_automation_condition()
_UNION_RELATIONS_CONDITION = dbt_union_relations_automation_condition()
_ALL_VIEWS_CODE_VERSION_CONDITION = _build_dbt_condition(
    _build_any_ancestor_code_version_changed()
)


class _EvaluationTimeout(Exception):
    pass


@contextmanager
def _timeout(seconds: int):
    """Context manager that raises _EvaluationTimeout after `seconds`."""

    def _handler(signum, frame):
        raise _EvaluationTimeout

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _uid_to_key(unique_id: str) -> AssetKey:
    return AssetKey(unique_id.split(".")[1:])


def _is_union_relations(props: dict) -> bool:
    return props.get("config", {}).get(
        "materialized"
    ) == "view" and "union_relations" in props.get("raw_code", "")


@pytest.fixture(scope="module")
def manifest():
    from teamster.code_locations.kipptaf import DBT_PROJECT

    return json.loads(DBT_PROJECT.manifest_path.read_text())


@pytest.fixture(scope="module")
def graph_info(manifest):
    """Pre-compute node metadata needed by all strategies."""
    nodes = manifest["nodes"]
    sources = manifest.get("sources", {})
    valid_ids = set(nodes.keys()) | set(sources.keys())

    node_meta = {}
    for uid, props in nodes.items():
        materialized = props.get("config", {}).get("materialized", "")
        dep_ids = [
            d for d in props.get("depends_on", {}).get("nodes", []) if d in valid_ids
        ]
        node_meta[uid] = {
            "materialized": materialized,
            "is_union_relations": _is_union_relations(props),
            "dep_keys": [_uid_to_key(d) for d in dep_ids],
        }

    source_keys = {_uid_to_key(uid) for uid in sources}

    return {
        "node_meta": node_meta,
        "source_keys": source_keys,
        "count_views": sum(
            1 for m in node_meta.values() if m["materialized"] == "view"
        ),
        "count_tables": sum(
            1 for m in node_meta.values() if m["materialized"] == "table"
        ),
        "count_union_relations": sum(
            1 for m in node_meta.values() if m["is_union_relations"]
        ),
    }


def _build_definitions(graph_info: dict, strategy: str) -> Definitions:
    """Build Dagster Definitions for the full kipptaf dbt graph."""
    node_meta = graph_info["node_meta"]
    source_keys = graph_info["source_keys"]

    source_specs = [AssetSpec(key=k) for k in source_keys]

    node_specs = []
    for uid, meta in node_meta.items():
        key = _uid_to_key(uid)
        materialized = meta["materialized"]
        dep_keys = meta["dep_keys"]

        if materialized in ("view", "ephemeral"):
            tags = _VIEW_TAG
            if strategy == "baseline":
                condition = _VIEW_CONDITION
            elif strategy == "union_relations_only":
                condition = (
                    _UNION_RELATIONS_CONDITION
                    if meta["is_union_relations"]
                    else _VIEW_CONDITION
                )
            elif strategy == "all_views":
                condition = _ALL_VIEWS_CODE_VERSION_CONDITION
            else:
                msg = f"Unknown strategy: {strategy}"
                raise ValueError(msg)
        elif materialized in ("table", "incremental"):
            tags = _TABLE_TAG
            condition = _TABLE_CONDITION
        else:
            tags = {}
            condition = None

        node_specs.append(
            AssetSpec(
                key=key,
                deps=dep_keys,
                tags=tags,
                automation_condition=condition,
            )
        )

    return Definitions(assets=[*source_specs, *node_specs])


def _evaluate_strategy(graph_info: dict, strategy: str) -> dict:
    """Evaluate a strategy and return timing results.

    Returns a dict with cold_elapsed, warm_elapsed (or None if timed out).
    """
    defs = _build_definitions(graph_info, strategy)
    instance = DagsterInstance.ephemeral()

    cold_elapsed = None
    warm_elapsed = None

    try:
        with _timeout(_EVALUATION_TIMEOUT_SECONDS):
            start = time.perf_counter()
            r1 = evaluate_automation_conditions(defs=defs, instance=instance)
            cold_elapsed = time.perf_counter() - start
    except _EvaluationTimeout:
        return {"cold_elapsed": None, "warm_elapsed": None, "timed_out": "cold"}

    try:
        with _timeout(_EVALUATION_TIMEOUT_SECONDS):
            start = time.perf_counter()
            evaluate_automation_conditions(
                defs=defs, instance=instance, cursor=r1.cursor
            )
            warm_elapsed = time.perf_counter() - start
    except _EvaluationTimeout:
        return {
            "cold_elapsed": cold_elapsed,
            "warm_elapsed": None,
            "timed_out": "warm",
        }

    return {
        "cold_elapsed": cold_elapsed,
        "warm_elapsed": warm_elapsed,
        "timed_out": None,
    }


def _count_condition_nodes(condition) -> int:
    """Count total nodes in a condition tree (proxy for evaluation cost)."""
    if condition is None:
        return 0
    count = 1
    for child in getattr(condition, "children", []):
        count += _count_condition_nodes(child)
    return count


def _format_time(seconds: float | None) -> str:
    if seconds is None:
        return f">{_EVALUATION_TIMEOUT_SECONDS}s"
    return f"{seconds:.3f}s"


class TestAutomationConditionPerformance:
    """Benchmark automation condition evaluation for the full kipptaf DAG.

    Three strategies are compared:
    - baseline: views get dbt_view_automation_condition() only
    - union_relations_only: union_relations views get recursive ancestor
      code_version_changed (current state after PR #3440)
    - all_views: ALL views get recursive ancestor code_version_changed
    """

    @pytest.fixture(scope="class")
    def results(self, graph_info):
        """Run all three strategies and collect timing results."""
        results = {}
        for strategy in ["baseline", "union_relations_only", "all_views"]:
            results[strategy] = _evaluate_strategy(graph_info, strategy)
        return results

    def test_report_performance(self, graph_info, results):
        """Report performance metrics for all three strategies."""
        view_tree = _count_condition_nodes(_VIEW_CONDITION)
        union_tree = _count_condition_nodes(_UNION_RELATIONS_CONDITION)
        all_views_tree = _count_condition_nodes(_ALL_VIEWS_CODE_VERSION_CONDITION)
        table_tree = _count_condition_nodes(_TABLE_CONDITION)

        print("\n")
        print("=" * 80)
        print("AUTOMATION CONDITION EVALUATION PERFORMANCE — kipptaf")
        print("=" * 80)
        print(
            f"Asset graph: {graph_info['count_views']} views, "
            f"{graph_info['count_tables']} tables, "
            f"{graph_info['count_union_relations']} union_relations, "
            f"{len(graph_info['source_keys'])} sources"
        )
        print(f"Evaluation timeout: {_EVALUATION_TIMEOUT_SECONDS}s per phase")
        print(f"Sensor budget: {_SENSOR_BUDGET_SECONDS}s")
        print()

        print("Condition tree sizes (nodes per condition):")
        print(f"  view (baseline):        {view_tree:>5}")
        print(f"  union_relations:        {union_tree:>5}")
        print(f"  all_views:              {all_views_tree:>5}")
        print(f"  table:                  {table_tree:>5}")
        print()

        print(f"{'Strategy':<25} {'Cold':>12} {'Warm':>12} {'Warm fits budget?':>20}")
        print("-" * 72)

        for strategy in ["baseline", "union_relations_only", "all_views"]:
            r = results[strategy]
            cold = _format_time(r["cold_elapsed"])
            warm = _format_time(r["warm_elapsed"])

            if r["warm_elapsed"] is not None:
                fits = "YES" if r["warm_elapsed"] < _SENSOR_BUDGET_SECONDS else "NO"
            else:
                fits = "NO (timed out)"

            print(f"{strategy:<25} {cold:>12} {warm:>12} {fits:>20}")

        # Relative cost
        baseline_warm = results["baseline"].get("warm_elapsed")
        if baseline_warm:
            print("\nRelative to baseline (warm):")
            for strategy in ["union_relations_only", "all_views"]:
                warm = results[strategy].get("warm_elapsed")
                if warm is not None:
                    print(f"  {strategy}: {warm / baseline_warm:.2f}x")
                else:
                    print(f"  {strategy}: timed out")

        print("=" * 80)

    def test_current_strategy_within_sensor_budget(self, results):
        """The current strategy (union_relations_only) must fit the sensor window."""
        r = results["union_relations_only"]
        assert r["warm_elapsed"] is not None, (
            "union_relations_only warm evaluation timed out"
        )
        assert r["warm_elapsed"] < _SENSOR_BUDGET_SECONDS, (
            f"union_relations_only warm evaluation took {r['warm_elapsed']:.3f}s, "
            f"exceeding {_SENSOR_BUDGET_SECONDS}s sensor budget"
        )

    def test_all_views_feasibility(self, results):
        """Report whether all_views strategy is feasible.

        This test documents the result — it does not assert pass/fail because
        the answer determines whether we can expand the recursive condition to
        all views or need a different approach.
        """
        r = results["all_views"]
        if r["warm_elapsed"] is None:
            print(
                f"\nall_views: INFEASIBLE — timed out after "
                f"{_EVALUATION_TIMEOUT_SECONDS}s"
            )
            if r["cold_elapsed"] is not None:
                print(f"  (cold evaluation completed in {r['cold_elapsed']:.3f}s)")
            pytest.skip(
                f"all_views timed out after {_EVALUATION_TIMEOUT_SECONDS}s — "
                f"infeasible for {_SENSOR_BUDGET_SECONDS}s sensor budget"
            )
        elif r["warm_elapsed"] >= _SENSOR_BUDGET_SECONDS:
            print(
                f"\nall_views: INFEASIBLE — warm={r['warm_elapsed']:.3f}s "
                f"exceeds {_SENSOR_BUDGET_SECONDS}s budget"
            )
            pytest.skip(f"all_views warm={r['warm_elapsed']:.3f}s exceeds budget")
        else:
            print(
                f"\nall_views: FEASIBLE — warm={r['warm_elapsed']:.3f}s "
                f"within {_SENSOR_BUDGET_SECONDS}s budget"
            )
