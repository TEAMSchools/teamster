# forked from .venv/lib/python3.10/site-packages/dagster_dbt/core/resources_v2.py
# until https://github.com/dagster-io/dagster/pull/15466 is merged in 1.4.2
import os
from contextlib import suppress
from pathlib import Path
from typing import Any, List, Mapping, Optional

from dagster import AssetsDefinition, OpExecutionContext
from dagster import _check as check
from dagster._core.errors import DagsterInvalidPropertyError
from dagster_dbt import DagsterDbtTranslator, DbtCliInvocation, DbtCliResource
from dagster_dbt.asset_utils import get_manifest_and_translator_from_dbt_assets
from dagster_dbt.core.resources_v2 import get_node_info_by_output_name, logger


def get_subset_selection_for_context(
    context: OpExecutionContext,
    manifest: Mapping[str, Any],
    select: Optional[str],
    exclude: Optional[str],
) -> List[str]:
    default_dbt_selection = []
    if select:
        default_dbt_selection += ["--select", select]
    if exclude:
        default_dbt_selection += ["--exclude", exclude]

    node_info_by_output_name = get_node_info_by_output_name(manifest)

    is_subsetted_execution = len(context.selected_output_names) != len(
        context.assets_def.node_keys_by_output_name
    )
    if not is_subsetted_execution:
        logger.info(
            "A dbt subsetted execution is not being performed. Using the default dbt "
            f"selection arguments `{default_dbt_selection}`."
        )
        return default_dbt_selection

    selected_dbt_resources = []
    for output_name in context.selected_output_names:
        node_info = node_info_by_output_name[output_name]

        fqn_selector = f"fqn:{'.'.join(node_info['fqn'])}"

        selected_dbt_resources.append(fqn_selector)

    union_selected_dbt_resources = ["--select"] + [" ".join(selected_dbt_resources)]

    logger.info(
        "A dbt subsetted execution is being performed. Overriding default dbt selection"
        f" arguments `{default_dbt_selection}` with arguments: "
        f"`{union_selected_dbt_resources}`"
    )

    return union_selected_dbt_resources


class DbtCliResource(DbtCliResource):
    def cli(
        self,
        args: List[str],
        *,
        raise_on_error: bool = True,
        manifest: Mapping[str, Any] | None = None,
        dagster_dbt_translator: DagsterDbtTranslator | None = None,
        context: OpExecutionContext | None = None,
    ) -> DbtCliInvocation:
        target_path = self._get_unique_target_path(context=context)
        env = {
            **os.environ.copy(),
            "PYTHONUNBUFFERED": "1",
            "DBT_LOG_FORMAT": "json",
            "DBT_TARGET_PATH": target_path,
        }

        assets_def: Optional[AssetsDefinition] = None
        with suppress(DagsterInvalidPropertyError):
            assets_def = context.assets_def if context else None

        if context and assets_def is not None:
            (
                manifest,
                dagster_dbt_translator,
            ) = get_manifest_and_translator_from_dbt_assets([assets_def])
            selection_args = get_subset_selection_for_context(
                context=context,
                manifest=manifest,
                select=context.op.tags.get("dagster-dbt/select"),
                exclude=context.op.tags.get("dagster-dbt/exclude"),
            )
        else:
            selection_args: List[str] = []
            if manifest is None:
                check.failed(
                    "Must provide a value for the manifest argument if not executing "
                    "as part of @dbt_assets"
                )
            dagster_dbt_translator = dagster_dbt_translator or DagsterDbtTranslator()

        profile_args: List[str] = []
        if self.profile:
            profile_args = ["--profile", self.profile]

        if self.target:
            profile_args += ["--target", self.target]

        args = ["dbt"] + self.global_config_flags + args + profile_args + selection_args
        project_dir = Path(self.project_dir).resolve(strict=True)

        return DbtCliInvocation.run(
            args=args,
            env=env,
            manifest=manifest,
            dagster_dbt_translator=dagster_dbt_translator,
            project_dir=project_dir,
            target_path=project_dir.joinpath(target_path),
            raise_on_error=raise_on_error,
        )
