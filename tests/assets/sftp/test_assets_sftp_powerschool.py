from dagster import AssetsDefinition, materialize


def _test_asset(assets: list[AssetsDefinition], selection: str):
    from teamster.core.resources import SSH_COUCHDROP, get_io_manager_gcs_avro

    result = materialize(
        assets=assets,
        selection=selection,
        resources={
            "ssh_couchdrop": SSH_COUCHDROP,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
        },
    )

    assert result.success

    # asset_check_evaluation = result.get_asset_check_evaluations()[0]

    # extras = asset_check_evaluation.metadata.get("extras")

    # assert extras is not None
    # assert extras.text == ""


def test_powerschool_schools_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/schools")
