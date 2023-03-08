{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "studentid", "transformation": "extract", "type": "int_value"},
            {"name": "teacherid", "transformation": "extract", "type": "int_value"},
            {"name": "entry_time", "transformation": "extract", "type": "int_value"},
            {"name": "category", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "logtypeid", "transformation": "extract", "type": "int_value"},
            {
                "name": "student_number",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "discipline_felonyflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_likelyinjuryflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_schoolrulesvioflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_policeinvolvedflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_hearingofficerflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_gangrelatedflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_hatecrimeflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_alcoholrelatedflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_drugrelatedflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_weaponrelatedflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "discipline_moneylossvalue",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "discipline_durationassigned",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "discipline_durationactual",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "discipline_sequence",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
