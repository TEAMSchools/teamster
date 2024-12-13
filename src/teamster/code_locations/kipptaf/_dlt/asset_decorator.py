# forked from dagster_embedded_elt/dlt/asset_decorator.py

from typing import Any, Callable, Mapping

from dagster import AssetsDefinition, PartitionsDefinition
from dagster import _check as check
from dagster import multi_asset
from dagster_embedded_elt.dlt import build_dlt_asset_specs
from dagster_embedded_elt.dlt.translator import DagsterDltTranslator
from dlt.extract.source import DltSource
from dlt.pipeline.pipeline import Pipeline


def dlt_assets(
    *,
    dlt_source: DltSource,
    dlt_pipeline: Pipeline,
    name: str | None = None,
    group_name: str | None = None,
    dagster_dlt_translator: DagsterDltTranslator | None = None,
    partitions_def: PartitionsDefinition | None = None,
    op_tags: Mapping[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], AssetsDefinition]:
    dagster_dlt_translator = check.inst_param(
        dagster_dlt_translator or DagsterDltTranslator(),
        "dagster_dlt_translator",
        DagsterDltTranslator,
    )

    return multi_asset(
        name=name,
        group_name=group_name,
        can_subset=True,
        partitions_def=partitions_def,
        specs=build_dlt_asset_specs(
            dlt_source=dlt_source,
            dlt_pipeline=dlt_pipeline,
            dagster_dlt_translator=dagster_dlt_translator,
        ),
        op_tags=op_tags,
    )
