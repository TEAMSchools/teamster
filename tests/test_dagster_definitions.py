def _test_definitions_validate(kwargs):
    from dagster._cli.workspace.cli_target import get_workspace_from_kwargs

    from dagster import __version__, instance_for_test

    with instance_for_test() as instance:
        with get_workspace_from_kwargs(
            instance=instance, version=__version__, kwargs=kwargs
        ) as workspace:
            for code_location, entry in workspace.get_code_location_entries().items():
                assert not entry.load_error, (
                    f"Validation failed for code location {code_location} with "
                    f"exception: {entry.load_error.message}."
                )


def test_definitions_kipptaf():
    _test_definitions_validate(
        {"module_name": ("teamster.code_locations.kipptaf.definitions",)}
    )


def test_definitions_kippcamden():
    _test_definitions_validate(
        {"module_name": ("teamster.code_locations.kippcamden.definitions",)}
    )


def test_definitions_kippmiami():
    _test_definitions_validate(
        {"module_name": ("teamster.code_locations.kippmiami.definitions",)}
    )


def test_definitions_kippnewark():
    _test_definitions_validate(
        {"module_name": ("teamster.code_locations.kippnewark.definitions",)}
    )


def test_definitions_all():
    _test_definitions_validate(
        {
            "module_name": (
                "teamster.code_locations.kippcamden.definitions",
                "teamster.code_locations.kippmiami.definitions",
                "teamster.code_locations.kippnewark.definitions",
                "teamster.code_locations.kipptaf.definitions",
            )
        }
    )
