from teamster.libraries.core.utils.functions import regex_pattern_replace


def test_regex_pattern_replace():
    test_patterns = [
        r"(?P<school_year_term>\d+)\/\w+-\w+Grade(?P<grade_level_subject>\d)Science_StudentData_\d+\s[AP]M\.csv",
        r"(?P<school_year_term>\d+)\/[A-Z]+-[A-Z]+_(?P<grade_level_subject>[\w\.]+)EOC_StudentData_\d+\s[AP]M\.csv",
        r"'incomeformdata(?P<fiscal_year>\d{4})\.csv'",
        r"'persondata(?P<fiscal_year>\d{4})\.csv'",
        r"(?:(?P<academic_year>\w+)\/)?diagnostic_and_instruction_(?P<subject>\w+)_ytd_window\.csv",
        r"(?:(?P<academic_year>\w+)\/)?diagnostic_results_(?P<subject>\w+)\.csv",
        r"(?:(?P<academic_year>\w+)\/)?instructional_usage_data_(?P<subject>\w+)\.csv",
        r"(?:(?P<academic_year>\w+)\/)?personalized_instruction_by_lesson_(?P<subject>\w+)\.csv",
        r"(?P<subject>)_Dashboard_Standards_v2.csv",
        r"(?P<subject>)_SkillArea_v1.csv",
        r"(?P<subject>).csv",
        r"\d+\/PM\d\/\w+-\w+(?P<grade_level_subject>Grade\dFAST[A-Za-z]+)_StudentData_(?P<school_year_term>SY\d+PM\d)\.csv",
        r"FL_FAST_(?P<subject>)_K-2.csv",
        r"FSA_(?P<school_year_term>\d+)SPR_\d+_SRS-E_(?P<grade_level_subject>\w+)_SCHL\.csv",
        r"njs(?P<fiscal_year>\d+)_NJ-\d+_\w+\.csv",
        r"PC_pcspr(?P<fiscal_year>\d+)_NJ-\d+(?:-\d+)?_\w+\.csv",
        r"pcspr(?P<fiscal_year>\d+)_NJ-\d+(?:-\d+)?_\w+\.csv",
    ]

    for test_pattern in test_patterns:
        result_pattern = regex_pattern_replace(
            pattern=test_pattern,
            replacements={
                "fiscal_year": "9999",
                "academic_year": "9999",
                "school_year_term": "9999",
                "subject": "SPAM",
                "grade_level_subject": "SPAM",
            },
        )

        print(f"{test_pattern}\n\t=> {result_pattern}\n")
        assert "?P<" not in result_pattern


def test_foo():
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
