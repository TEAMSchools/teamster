{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "teacherid", "extract": "int_value"},
            {"name": "entry_time", "extract": "int_value"},
            {"name": "category", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "logtypeid", "extract": "int_value"},
            {
                "name": "student_number",
                "extract": "double_value",
            },
            {
                "name": "discipline_felonyflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_likelyinjuryflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_schoolrulesvioflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_policeinvolvedflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_hearingofficerflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_gangrelatedflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_hatecrimeflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_alcoholrelatedflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_drugrelatedflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_weaponrelatedflag",
                "extract": "int_value",
            },
            {
                "name": "discipline_moneylossvalue",
                "extract": "double_value",
            },
            {
                "name": "discipline_durationassigned",
                "extract": "double_value",
            },
            {
                "name": "discipline_durationactual",
                "extract": "double_value",
            },
            {
                "name": "discipline_sequence",
                "extract": "int_value",
            },
        ],
    )
}}
