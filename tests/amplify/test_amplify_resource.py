import pathlib

from dagster import EnvVar, build_resources

from teamster.core.amplify.resources import MClassResource


def _test(dyd_results, years):
    with build_resources(
        resources={
            "mclass": MClassResource(
                username=EnvVar("AMPLIFY_USERNAME"), password=EnvVar("AMPLIFY_PASSWORD")
            )
        }
    ) as resources:
        mclass: MClassResource = resources.mclass

    response = mclass.post(
        path="reports/api/report/downloadyourdata",
        data={
            "data": {
                "accounts": "1300588536",
                "districts": "1300588535",
                "roster_option": "2",
                "dyd_assessments": "7_D8",
                "tracking_id": None,
                "dyd_results": dyd_results,
                "years": years,
            }
        },
    )

    file_path = pathlib.Path("env/amplify") / (dyd_results + ".csv")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.open(mode="w").writelines(response.text)


def test_benchmark_student_summary():
    _test(
        dyd_results="BM",
        years="22",  # 2023-2024
    )


# def test_pm_student_summary():
#     _test(
#         dyd_results="PM",
#         years="22",  # 2023-2024
#     )
