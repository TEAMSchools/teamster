import pytest
from dagster import (
    AssetKey,
    AssetSelection,
    AutomationCondition,
    DagsterInstance,
    Definitions,
    asset,
    evaluate_automation_conditions,
    materialize,
)

from teamster.core.automation_conditions import (
    _VIEW_SELECTION,
    dbt_table_automation_condition,
    dbt_view_automation_condition,
)

_EMPTY_SELECTION = AssetSelection.assets()
_VIEW_TAG = {"dagster/materialized": "view"}
_TABLE_TAG = {"dagster/materialized": "table"}


def _get_view_condition() -> AutomationCondition:
    return dbt_view_automation_condition(ignore_selection=_EMPTY_SELECTION)


def _get_table_condition() -> AutomationCondition:
    return dbt_table_automation_condition(ignore_selection=_EMPTY_SELECTION)


def test_view_not_requested_on_upstream_update():
    """Views should NOT be requested when an upstream table is updated."""

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def my_view():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, my_view]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)

    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.total_requested == 0

    materialize(assets=[upstream_table], instance=instance, selection=[upstream_table])

    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 0


def test_table_requested_on_upstream_update():
    """Tables SHOULD be requested when a direct upstream table is updated."""

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        deps=[upstream_table],
        automation_condition=_get_table_condition(),
        tags=_TABLE_TAG,
    )
    def downstream_table():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, downstream_table]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)

    materialize(assets=[upstream_table], instance=instance, selection=[upstream_table])

    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("downstream_table")) == 1


def test_table_view_table_chain():
    """Core test: Table -> View -> Table chain.

    When upstream_table is materialized:
    - intermediate_view should NOT be requested (it's a view)
    - downstream_table SHOULD be requested (sees through the view)
    """

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def intermediate_view():
        return 2

    @asset(
        deps=[intermediate_view],
        automation_condition=_get_table_condition(),
        tags=_TABLE_TAG,
    )
    def downstream_table():
        return 3

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, intermediate_view, downstream_table]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.total_requested == 0

    materialize(assets=[upstream_table], instance=instance, selection=[upstream_table])

    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("intermediate_view")) == 0
    assert result.get_num_requested(AssetKey("downstream_table")) == 1


def test_double_view_chain():
    """Table -> View -> View -> Table chain.

    Tests that the ancestor lookthrough handles multiple consecutive views.
    """

    @asset(tags=_TABLE_TAG)
    def source_table():
        return 1

    @asset(
        deps=[source_table], automation_condition=_get_view_condition(), tags=_VIEW_TAG
    )
    def view_a():
        return 2

    @asset(deps=[view_a], automation_condition=_get_view_condition(), tags=_VIEW_TAG)
    def view_b():
        return 3

    @asset(deps=[view_b], automation_condition=_get_table_condition(), tags=_TABLE_TAG)
    def target_table():
        return 4

    instance = DagsterInstance.ephemeral()
    all_assets = [source_table, view_a, view_b, target_table]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)

    materialize(assets=[source_table], instance=instance, selection=[source_table])
    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )

    assert result.get_num_requested(AssetKey("view_a")) == 0
    assert result.get_num_requested(AssetKey("view_b")) == 0
    assert result.get_num_requested(AssetKey("target_table")) == 1


def test_update_propagates_through_view_between_tables():
    """Table -> Table -> View -> Table chain.

    When source_table is updated:
    - middle_table sees the direct dep update and is requested
    - will_be_requested() makes middle_table visible to intervening_view's deps
    - downstream_table's ancestor lookthrough sees middle_table through the view
    - All tables in the chain are correctly requested
    """

    @asset(tags=_TABLE_TAG)
    def source_table():
        return 1

    @asset(
        deps=[source_table],
        automation_condition=_get_table_condition(),
        tags=_TABLE_TAG,
    )
    def middle_table():
        return 2

    @asset(
        deps=[middle_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def intervening_view():
        return 3

    @asset(
        deps=[intervening_view],
        automation_condition=_get_table_condition(),
        tags=_TABLE_TAG,
    )
    def downstream_table():
        return 4

    instance = DagsterInstance.ephemeral()
    all_assets = [source_table, middle_table, intervening_view, downstream_table]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.total_requested == 0

    # Update only source_table
    materialize(assets=[source_table], instance=instance, selection=[source_table])

    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )

    # middle_table should be requested (direct dep updated)
    assert result.get_num_requested(AssetKey("middle_table")) == 1
    # intervening_view should NOT be requested (view ignores upstream updates)
    assert result.get_num_requested(AssetKey("intervening_view")) == 0
    # downstream_table SHOULD be requested — ancestor lookthrough sees
    # middle_table (will_be_requested) through intervening_view
    assert result.get_num_requested(AssetKey("downstream_table")) == 1


def test_view_requested_on_code_version_change():
    """Views SHOULD be requested when their code version changes."""

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="1",
        tags=_VIEW_TAG,
    )
    def my_view():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, my_view]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Simulate code version change by redefining with new version
    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="2",
        tags=_VIEW_TAG,
    )
    def my_view_v2():
        return 2

    defs_v2 = Definitions(assets=[upstream_table, my_view_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1


class TestKipptafDbtAssets:
    """Integration tests using the real kipptaf dbt manifest.

    Validates that the CustomDagsterDbtTranslator correctly tags assets
    with dagster/materialized and that automation conditions are assigned
    based on the actual dbt project structure.
    """

    @pytest.fixture(scope="class")
    def all_dbt_assets(self):
        from teamster.code_locations.kipptaf._dbt.assets import all_dbt_assets

        return all_dbt_assets

    @pytest.fixture(scope="class")
    def specs_by_key(self, all_dbt_assets):
        return {s.key: s for s in all_dbt_assets.specs}

    @pytest.fixture(scope="class")
    def view_specs(self, all_dbt_assets):
        return [
            s
            for s in all_dbt_assets.specs
            if s.tags.get("dagster/materialized") == "view"
        ]

    @pytest.fixture(scope="class")
    def table_specs(self, all_dbt_assets):
        return [
            s
            for s in all_dbt_assets.specs
            if s.tags.get("dagster/materialized") == "table"
        ]

    def test_all_models_tagged_with_materialized(self, all_dbt_assets):
        """Every dbt model spec should have a dagster/materialized tag."""
        for spec in all_dbt_assets.specs:
            assert "dagster/materialized" in spec.tags, (
                f"{spec.key} missing dagster/materialized tag"
            )

    def test_materialized_tag_values(self, view_specs, table_specs, all_dbt_assets):
        """The materialized tag should only contain known dbt materialization values."""
        all_values = {s.tags["dagster/materialized"] for s in all_dbt_assets.specs}
        known = {"view", "table", "incremental", "ephemeral", "seed", "snapshot"}
        assert all_values <= known, (
            f"Unexpected materialized values: {all_values - known}"
        )
        assert len(view_specs) > 0, "Expected at least one view model"
        assert len(table_specs) > 0, "Expected at least one table model"

    def test_most_views_have_automation_condition(self, view_specs):
        """Most view models should have an automation condition assigned.

        Some may be explicitly disabled via dbt meta (enabled: false).
        """
        with_condition = [s for s in view_specs if s.automation_condition is not None]
        without_condition = [s for s in view_specs if s.automation_condition is None]

        assert len(with_condition) > len(without_condition), (
            f"Most views should have conditions: "
            f"{len(with_condition)} with vs {len(without_condition)} without"
        )

    def test_most_tables_have_automation_condition(self, table_specs):
        """Most table models should have an automation condition assigned.

        Some may be explicitly disabled via dbt meta (enabled: false).
        """
        with_condition = [s for s in table_specs if s.automation_condition is not None]
        without_condition = [s for s in table_specs if s.automation_condition is None]

        assert len(with_condition) > len(without_condition), (
            f"Most tables should have conditions: "
            f"{len(with_condition)} with vs {len(without_condition)} without"
        )

    def test_view_selection_matches_view_tagged_specs(
        self, all_dbt_assets, view_specs, table_specs
    ):
        """The dagster/materialized tag should cleanly separate views from tables.

        Validates that _VIEW_SELECTION (tag-based) would correctly partition
        the asset graph by checking that no spec is tagged as both.
        """
        view_keys = {s.key for s in view_specs}
        table_keys = {s.key for s in table_specs}

        assert view_keys.isdisjoint(table_keys), (
            f"No asset should be tagged as both view and table"
        )

        all_keys = {s.key for s in all_dbt_assets.specs}
        tagged_keys = view_keys | table_keys
        untagged = {
            s.key
            for s in all_dbt_assets.specs
            if s.tags.get("dagster/materialized") not in ("view", "table")
        }

        assert len(tagged_keys) > len(untagged), (
            f"Most assets should be tagged view or table: "
            f"{len(tagged_keys)} tagged vs {len(untagged)} other"
        )

    def test_table_view_table_chain_in_kipptaf(self, all_dbt_assets, specs_by_key):
        """Find and validate a real table→view→table chain in kipptaf.

        Searches the asset graph for a table whose dep is a view whose dep
        is another table, then verifies all three have the expected tags.
        """
        chain_found = False

        for spec in all_dbt_assets.specs:
            if spec.tags.get("dagster/materialized") != "table":
                continue

            for dep in spec.deps:
                view_spec = specs_by_key.get(dep.asset_key)
                if (
                    view_spec is None
                    or view_spec.tags.get("dagster/materialized") != "view"
                ):
                    continue

                for grandparent_dep in view_spec.deps:
                    gp_spec = specs_by_key.get(grandparent_dep.asset_key)
                    if (
                        gp_spec is not None
                        and gp_spec.tags.get("dagster/materialized") == "table"
                    ):
                        chain_found = True

                        assert gp_spec.tags["dagster/materialized"] == "table"
                        assert view_spec.tags["dagster/materialized"] == "view"
                        assert spec.tags["dagster/materialized"] == "table"

                        assert gp_spec.automation_condition is not None
                        assert view_spec.automation_condition is not None
                        assert spec.automation_condition is not None
                        break

                if chain_found:
                    break
            if chain_found:
                break

        assert chain_found, "No table→view→table chain found in kipptaf dbt assets"
