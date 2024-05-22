from dagster import AssetExecutionContext, asset, materialize

from teamster.amplify.dibels.resources import DibelsDataSystemResource


@asset
def foo(context: AssetExecutionContext, dds: DibelsDataSystemResource):
    dds.report(
        report="DataFarming",
        scope="District",
        district=109,
        grade="_ALL_",
        start_year=2023,
        end_year=2023,
        assessment=15030,
        assessment_period="_ALL_",
        student_filter="none",
        growth_measure=16240,
        delimiter=0,
        fields=[
            1,
            2,
            3,
            4,
            5,
            21,
            22,
            23,
            25,
            26,
            27,
            41,
            43,
            44,
            45,
            47,
            48,
            49,
            51,
            50,
            61,
            62,
        ],
    )


def test_foo():
    result = materialize(
        assets=[foo],
        resources={"dds": DibelsDataSystemResource(username="", password="")},
    )

    assert result.success
