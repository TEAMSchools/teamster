from typing import List, Sequence

from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    AssetSpec,
    DagsterInvariantViolationError,
    _check,
    multi_asset,
)
from dagster._core.definitions.asset_spec import (
    SYSTEM_METADATA_KEY_ASSET_EXECUTION_TYPE,
    AssetExecutionType,
)
from dagster._utils.warnings import disable_dagster_warnings


def external_assets_from_specs(
    specs: Sequence[AssetSpec], compute_kind: str | None = None
) -> List[AssetsDefinition]:
    assets_defs = []
    for spec in specs:
        _check.invariant(
            spec.auto_materialize_policy is None,
            "auto_materialize_policy must be None since it is ignored",
        )
        _check.invariant(
            spec.code_version is None, "code_version must be None since it is ignored"
        )
        _check.invariant(
            spec.skippable is False,
            "skippable must be False since it is ignored and False is the default",
        )

        with disable_dagster_warnings():

            @multi_asset(
                name=spec.key.to_python_identifier(),
                compute_kind=compute_kind,
                specs=[
                    AssetSpec.dagster_internal_init(
                        key=spec.key,
                        description=spec.description,
                        group_name=spec.group_name,
                        freshness_policy=spec.freshness_policy,
                        metadata={
                            **(spec.metadata or {}),
                            **{
                                SYSTEM_METADATA_KEY_ASSET_EXECUTION_TYPE: (
                                    AssetExecutionType.UNEXECUTABLE.value
                                )
                            },
                        },
                        deps=spec.deps,
                        tags=spec.tags,
                        owners=spec.owners,
                        skippable=False,
                        code_version=None,
                        auto_materialize_policy=None,
                    )
                ],
            )
            def _external_assets_def(context: AssetExecutionContext) -> None:
                raise DagsterInvariantViolationError(
                    "You have attempted to execute an unexecutable asset"
                    f" {context.asset_key.to_user_string}."
                )

            assets_defs.append(_external_assets_def)

    return assets_defs
