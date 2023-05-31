import pathlib

from dagster import EnvVar, build_resources

from teamster.core.amplify.resources import MClassResource


def test_resource():
    with build_resources(
        resources={
            "amplify": MClassResource(
                username=EnvVar("AMPLIFY_USERNAME"), password=EnvVar("AMPLIFY_PASSWORD")
            )
        }
    ) as resources:
        mclass: MClassResource = resources.mclass

        for dyd in [
            {"key": "BM", "url": "benchmark_student_summary"},
            {"key": "PM", "url": "pm_student_summary"},
        ]:
            file_path = pathlib.Path("env") / (dyd["url"] + ".csv")

            response = mclass.post(
                path="reports/api/report/downloadyourdata",
                data={
                    "data": {
                        "accounts": "1187882003",
                        "districts": "1294940238",
                        "dyd_assessments": "7_D8",  # DIBELS 8th Edition
                        "roster_option": "2",  # On Test Day
                        "tracking_id": None,
                        "years": "21",  # 2022-2023
                        "dyd_results": dyd["key"],
                    }
                },
            )

            with file_path.open(mode="w") as f:
                f.write(response.text)
