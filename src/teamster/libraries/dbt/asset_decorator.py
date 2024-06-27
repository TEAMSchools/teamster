from typing import Any, Callable

from dagster import (
    AssetsDefinition,
    BackfillPolicy,
    DagsterInvalidDefinitionError,
    PartitionsDefinition,
    RetryPolicy,
    TimeWindowPartitionsDefinition,
    multi_asset,
)
from dagster._utils.warnings import suppress_dagster_warnings
from dagster_dbt import DagsterDbtTranslator, DbtProject
from dagster_dbt.asset_utils import (
    DAGSTER_DBT_EXCLUDE_METADATA_KEY,
    DAGSTER_DBT_SELECT_METADATA_KEY,
    build_dbt_multi_asset_args,
)
from dagster_dbt.dagster_dbt_translator import validate_translator
from dagster_dbt.dbt_manifest import DbtManifestParam, validate_manifest

from teamster.libraries.dbt.asset_utils import build_dbt_multi_asset_deps


@suppress_dagster_warnings
def dbt_external_source_assets(
    *,
    manifest: DbtManifestParam,
    select: str = "fqn:*",
    exclude: str | None = None,
    name: str | None = None,
    io_manager_key: str | None = None,
    partitions_def: PartitionsDefinition | None = None,
    dagster_dbt_translator: DagsterDbtTranslator | None = None,
    backfill_policy: BackfillPolicy | None = None,
    op_tags: dict[str, Any] | None = None,
    required_resource_keys: set[str] | None = None,
    project: DbtProject | None = None,
    retry_policy: RetryPolicy | None = None,
) -> Callable[[Callable[..., Any]], AssetsDefinition]:
    """Forked from dagster_dbt.asset_decorator.dbt_assets"""
    dagster_dbt_translator = validate_translator(
        dagster_dbt_translator or DagsterDbtTranslator()
    )
    manifest = validate_manifest(manifest)

    (
        _deps,
        outs,
        _internal_asset_deps,
        check_specs,
    ) = build_dbt_multi_asset_args(
        manifest=manifest,
        dagster_dbt_translator=dagster_dbt_translator,
        select=select,
        exclude=exclude or "",
        io_manager_key=io_manager_key,
        project=project,
    )

    deps, internal_asset_deps = build_dbt_multi_asset_deps(
        manifest=manifest,
        dagster_dbt_translator=dagster_dbt_translator,
        select=select,
        exclude=exclude or "",
        project=project,
    )

    if op_tags and DAGSTER_DBT_SELECT_METADATA_KEY in op_tags:
        raise DagsterInvalidDefinitionError(
            "To specify a dbt selection, use the 'select' argument, not "
            f"'{DAGSTER_DBT_SELECT_METADATA_KEY}' with op_tags"
        )

    if op_tags and DAGSTER_DBT_EXCLUDE_METADATA_KEY in op_tags:
        raise DagsterInvalidDefinitionError(
            "To specify a dbt exclusion, use the 'exclude' argument, not "
            f"'{DAGSTER_DBT_EXCLUDE_METADATA_KEY}' with op_tags"
        )

    resolved_op_tags = {
        **({DAGSTER_DBT_SELECT_METADATA_KEY: select} if select else {}),
        **({DAGSTER_DBT_EXCLUDE_METADATA_KEY: exclude} if exclude else {}),
        **(op_tags if op_tags else {}),
    }

    if (
        partitions_def
        and isinstance(partitions_def, TimeWindowPartitionsDefinition)
        and not backfill_policy
    ):
        backfill_policy = BackfillPolicy.single_run()

    return multi_asset(
        outs=outs,
        name=name,
        internal_asset_deps=internal_asset_deps,
        deps=deps,
        required_resource_keys=required_resource_keys,
        compute_kind="dbt",
        partitions_def=partitions_def,
        can_subset=True,
        op_tags=resolved_op_tags,
        check_specs=check_specs,
        backfill_policy=backfill_policy,
        retry_policy=retry_policy,
    )
