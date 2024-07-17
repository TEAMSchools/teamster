import re


def test_regex_pattern_replace():
    from teamster.libraries.core.utils.functions import regex_pattern_replace

    test_patterns = [
        r"(?P<fiscal_year>\d+)_NJ-\d+-\d+_\w+GPA\w+\.csv",
        r"(?P<subject>)_Dashboard_Standards_v2\.csv",
        r"(?P<subject>)_SkillArea_v1\.csv",
        r"(?P<subject>)\.csv" r"(?P<subject>)\.csv",
        r"{remote_dir_regex_prefix}/student_list_report/(?P<test_type>[a-z]+)",
        r"/data-team/kippmiami/fldoe/eoc/(?P<school_year_term>\d+)",
        r"/data-team/kippmiami/fldoe/fast/(?P<school_year_term>\d+/PM\d)",
        r"/data-team/kippmiami/fldoe/science/(?P<school_year_term>\d+)",
        r"/data-team/kipptaf/performance-management/observation-details/(?P<academic_year>\d+)/(?P<term>PM\d)",
        r"/exports/fl-kipp_miami/(?P<academic_year>\w+)"
        r"/exports/nj-kipp_nj/(?P<academic_year>\w+)",
        r"\w+-\w+_(?P<grade_level_subject>[\w\.]+)EOC_StudentData_\d+\s[AP]M\.csv",
        r"\w+-\w+_(?P<grade_level_subject>Grade\dFAST\w+)_StudentData_.+\.csv",
        r"\w+-\w+_Grade(?P<grade_level_subject>\d)Science_StudentData_\d+\s[AP]M\.csv",
        r"adp_payroll_(?P<date>\d+)_(?P<group_code>\w+)\.csv",
        r"diagnostic_and_instruction_(?P<subject>\w+)_ytd_window\.csv",
        r"diagnostic_results_(?P<subject>\w+)\.csv",
        r"FL_FAST_(?P<subject>)_K-2\.csv",
        r"FSA_(?P<school_year_term>\d+)SPR_\d+_SRS-E_(?P<grade_level_subject>\w+)_SCHL\.csv",
        r"instructional_usage_data_(?P<subject>\w+)\.csv",
        r"njs(?P<fiscal_year>\d+)_NJ-\d+_\w+\.csv",
        r"PC_pcspr(?P<fiscal_year>\d+)_NJ-\d+(-\d+)?_\w+\.csv",
        r"pc(?P<administration>[a-z]+)"
        r"pc(?P<administration>[a-z]+)(?P<fiscal_year>\d+)_NJ-\d+(-\d+)?_\w+GPA\w+\.csv",
        r"pcspr(?P<fiscal_year>\d+)_NJ-\d+(-\d+)?_\w+\.csv",
        r"personalized_instruction_by_lesson_(?P<subject>\w+)\.csv",
        r"StudentListReport_(?P<administration_fiscal_year>[A-za-z]+\d+)_\d+_\d+-\d+-\d+\.csv",
        r"StudentListReport_(?P<administration_fiscal_year>[A-za-z]+\d+)(_\d+_|\s-\s)\d+-\d+-\d+(T\w+\.\d+\+\d+)?\.csv",
    ]
    for test_pattern in test_patterns:
        result_pattern = regex_pattern_replace(
            pattern=test_pattern,
            replacements={
                "fiscal_year": "9999",
                "academic_year": "9999",
                "school_year_term": "9999",
                "term": "SPAM",
                "subject": "SPAM",
                "grade_level_subject": "SPAM",
                "test_type": "SPAM",
                "date": "9999-99-99",
                "group_code": "SPAM",
                "administration": "SPAM",
                "administration_fiscal_year": "SPAM",
            },
        )

        print(f"{test_pattern}\n\t=> {result_pattern}\n")
        assert "?P<" not in result_pattern


def test_ghseet_asset_key_rename():
    from teamster.code_locations.kipptaf.dbt.assets import manifest

    asset_keys_old = set()
    asset_keys_new = set()

    for source in manifest["sources"].values():
        if (
            source.get("external")
            and source["external"]["options"]["format"] == "GOOGLE_SHEETS"
        ):
            asset_keys_old.add(
                str(["kipptaf", source["source_name"], source["name"].split("__")[-1]])
            )

            asset_keys_new.add(str(source["meta"]["dagster"]["parent_asset_key_path"]))

    assert asset_keys_new == asset_keys_old


def test_orjson():
    import json
    from datetime import date, datetime, timedelta
    from decimal import Decimal

    import orjson
    from pendulum import Date, DateTime, Duration

    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, (timedelta, Decimal, bytes, Duration)):
                return str(o)
            elif isinstance(o, (DateTime, Date)):
                return o.for_json()
            elif isinstance(o, (datetime, date)):
                return o.isoformat()
            else:
                return super().default(o)

    def orjson_default(obj):
        if isinstance(obj, (DateTime, Date)):
            return obj.for_json()
        else:
            raise TypeError

    obj = {
        "timedelta": timedelta(days=1),
        "Decimal": Decimal(1),
        "bytes": b"foo",
        "Duration": Duration(days=1),
        "DateTime": DateTime(year=9999, month=12, day=31),
        "Date": Date(year=9999, month=12, day=31),
        "datetime": datetime(year=9999, month=12, day=31),
        "date": date(year=9999, month=12, day=31),
    }

    stdlib_result = json.dumps(obj=obj, cls=CustomJSONEncoder)
    orjson_result = orjson.dumps(obj, default=orjson_default).decode()

    for k in obj.keys():
        pattern = rf'"{k}":\s?"([^"]*)",?'

        stdlib_match = re.search(pattern=pattern, string=stdlib_result)
        orjson_match = re.search(pattern=pattern, string=orjson_result)

        assert stdlib_match is not None
        assert orjson_match is not None

        assert stdlib_match.group(1) == orjson_match.group(1)
        print(f"{k}: {stdlib_match.group(1)} == {orjson_match.group(1)}")


def test_foo():
    from teamster.libraries.sftp.assets import compose_regex, match_files

    files = [
        (None, "\\./.DS_Store"),
        (None, "\\./additional_earnings_report.csv"),
        (None, "\\./comprehensive_benefits_report.csv"),
        (None, "\\./employees.csv"),
        (None, "\\./employees_all.csv"),
        (None, "\\./employees_future.csv"),
        (None, "\\./employee_onboarding.csv"),
        (None, "\\./home_cost_number.csv"),
        (None, "\\./manager_history.csv"),
        (None, "\\./pension_and_benefits_enrollments.csv"),
        (None, "\\./pension_and_benefits_enrollments_history.csv"),
        (None, "\\./restricted_grant_coding.csv"),
        (None, "\\./salary_history.csv"),
        (None, "\\./staff_roster_example.csv"),
        (None, "\\./status_history.csv"),
        (None, "\\./vaccine_records.csv"),
        (None, "\\./work_assignment_history.csv"),
    ]

    remote_dir_regex_composed = compose_regex(regexp=r"\.")
    remote_file_regex_composed = compose_regex(
        regexp=r"additional_earnings_report\.csv"
    )

    file_matches = match_files(
        remote_dir=remote_dir_regex_composed,
        remote_file=remote_file_regex_composed,
        files=files,
    )

    assert len(file_matches) > 0
