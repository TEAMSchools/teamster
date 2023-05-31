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


"""
{
    "resolved": {
        "accounts": [
            {"code": "1187882003", "name": "NATIONAL KIPP FOUNDATION", "selected": true}
        ],
        "districts": [
            {"code": "1294940238", "name": "KIPP New Jersey", "selected": true}
        ],
        "dyd_assessments": [
            {
                "children": [
                    {
                        "assmt_family_code": "RAI",
                        "assmt_family_version_code": "RAI",
                        "code": "RAI",
                        "default": false,
                        "grouped_item_rank": 3,
                        "name": "Remote Administration Indicator",
                        "rank": 0,
                        "selected": false,
                    }
                ],
                "code": "7_D8",
                "default": true,
                "dyd_tag_group": 1,
                "group_label": "DIBELS",
                "grouped_item_rank": 0,
                "name": "DIBELS 8th Edition",
                "rank": 0,
                "selected": true,
            }
        ],
        "dyd_performance_levels": null,
        "dyd_results": [
            {
                "abbrev": "Benchmark",
                "code": "BM",
                "key": "BM",
                "name": "Benchmark",
                "rank": "1",
                "selected": true,
                "url": "benchmark_student_summary",
            },
            {
                "abbrev": "Progress Monitoring",
                "code": "PM",
                "key": "PM",
                "name": "Progress Monitoring",
                "rank": "2",
                "selected": false,
                "url": "pm_student_summary",
            },
            {
                "abbrev": "Classroom Growth",
                "code": "PATHWAYS",
                "key": "PATHWAYS",
                "name": "Classroom Growth",
                "rank": "3",
                "selected": false,
                "url": "pathways_classroom_growth",
            },
            {
                "abbrev": "DIBELS Deep",
                "code": "D-DEEP",
                "key": "D-DEEP",
                "name": "DIBELS Deep",
                "rank": "4",
                "selected": false,
                "url": "benchmark_student_summary",
            },
        ],
        "grades": [
            {"abbrev": "Pre-K", "code": "1", "name": "Grade Pre-K", "selected": true},
            {"abbrev": "K", "code": "2", "name": "Grade K", "selected": true},
            {"abbrev": "1", "code": "3", "name": "Grade 1", "selected": true},
            {"abbrev": "2", "code": "4", "name": "Grade 2", "selected": true},
            {"abbrev": "3", "code": "5", "name": "Grade 3", "selected": true},
            {"abbrev": "4", "code": "6", "name": "Grade 4", "selected": true},
            {"abbrev": "5", "code": "7", "name": "Grade 5", "selected": true},
            {"abbrev": "6", "code": "8", "name": "Grade 6", "selected": true},
            {"abbrev": "7", "code": "9", "name": "Grade 7", "selected": true},
            {"abbrev": "8", "code": "10", "name": "Grade 8", "selected": true},
            {"abbrev": "9", "code": "11", "name": "Grade 9", "selected": true},
            {"abbrev": "10", "code": "12", "name": "Grade 10", "selected": true},
            {"abbrev": "11", "code": "13", "name": "Grade 11", "selected": true},
            {"abbrev": "12", "code": "14", "name": "Grade 12", "selected": true},
        ],
        "periods": [
            {
                "abbrev": "BOY",
                "code": "21_31",
                "name": "22-23 BOY",
                "rank": 21001,
                "selected": true,
                "years": {
                    "abbrev": "22-23",
                    "code": "21",
                    "name": "2022-2023",
                    "rank": 21,
                },
            },
            {
                "abbrev": "MOY",
                "code": "21_32",
                "name": "22-23 MOY",
                "rank": 21002,
                "selected": true,
                "years": {
                    "abbrev": "22-23",
                    "code": "21",
                    "name": "2022-2023",
                    "rank": 21,
                },
            },
            {
                "abbrev": "EOY",
                "code": "21_33",
                "name": "22-23 EOY",
                "rank": 21003,
                "selected": true,
                "years": {
                    "abbrev": "22-23",
                    "code": "21",
                    "name": "2022-2023",
                    "rank": 21,
                },
            },
        ],
        "pm_periods": null,
        "programs": null,
        "ready": [{"code": "YES", "name": "Ready", "selected": true}],
        "result": [
            {
                "code": "download_your_data",
                "selected": true,
                "value": "Download Your Data",
            }
        ],
        "roster_option": [
            {
                "code": "2",
                "enabled": true,
                "name": "On Test Day",
                "rank": "2",
                "selected": true,
            },
            {
                "code": "3",
                "enabled": true,
                "name": "Now",
                "rank": "1",
                "selected": false,
            },
        ],
        "school_grouping": [
            {"code": "3", "enabled": true, "name": "Districts", "selected": true}
        ],
        "schools": [
            {
                "code": "1294941070",
                "districts": [{"code": "1294940238", "name": "KIPP New Jersey"}],
                "name": "KIPP Lanning Square Primary",
                "selected": true,
            },
            {
                "code": "1294941069",
                "districts": [{"code": "1294940238", "name": "KIPP New Jersey"}],
                "name": "KIPP Seek Academy",
                "selected": true,
            },
            {
                "code": "1294941071",
                "districts": [{"code": "1294940238", "name": "KIPP New Jersey"}],
                "name": "KIPP Sumner Elementary",
                "selected": true,
            },
            {
                "code": "1294941072",
                "districts": [{"code": "1294940238", "name": "KIPP New Jersey"}],
                "name": "KIPP Truth Academy",
                "selected": true,
            },
            {
                "code": "1294941073",
                "districts": [{"code": "1294940238", "name": "KIPP New Jersey"}],
                "name": "KIPP Upper Roseville Academy",
                "selected": true,
            },
        ],
        "users": [
            {
                "code": "2668073",
                "current_year": {"code": "21", "name": "2022-2023"},
                "email": "dagster@apps.teamschools.org",
                "first_name": "Dagster",
                "home_inst": {
                    "accounts": {
                        "code": "1187882003",
                        "name": "NATIONAL KIPP FOUNDATION",
                    },
                    "districts": {"code": "1294940238", "name": "KIPP New Jersey"},
                },
                "initial_level": {
                    "grain": {
                        "code": "4",
                        "is_inst_level": true,
                        "label": "schools",
                        "name": "School",
                        "parameter": ["accounts", "districts", "schools"],
                    },
                    "school_grouping": {
                        "code": "3",
                        "enabled": true,
                        "name": "Districts",
                    },
                    "scope": {
                        "code": "2",
                        "label": "districts",
                        "name": "District",
                        "parameter": ["accounts", "districts"],
                    },
                },
                "is_teacher": false,
                "last_name": "Robot",
                "name": "Robot, Dagster",
                "selected": true,
                "staff_role": "System Access",
                "username": "dagster",
            }
        ],
        "years": [
            {
                "abbrev": "22-23",
                "assmt_products": ["3D8", "D8"],
                "code": "21",
                "name": "2022-2023",
                "rank": 21,
                "selected": true,
            }
        ],
    },
}
"""
