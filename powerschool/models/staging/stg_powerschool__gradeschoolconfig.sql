{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradeschoolconfigid",
        transform_cols=[
            {
                "name": "gradeschoolconfigid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "schoolsdcid", "transformation": "extract", "type": "int_value"},
            {"name": "yearid", "transformation": "extract", "type": "int_value"},
            {
                "name": "defaultdecimalcount",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "iscalcformulaeditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isdropscoreeditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "iscalcprecisioneditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "iscalcmetriceditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isrecentscoreeditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "ishigherstndautocalc",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "ishigherstndcalceditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "ishighstandardeditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "iscalcmetricschooledit",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isstandardsshown",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isstandardsshownonasgmt",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "istraditionalgradeshown",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "iscitizenshipdisplayed",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "termbinlockoffset",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "lockwarningoffset",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "issectstndweighteditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "minimumassignmentvalue",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isgradescaleteachereditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isstandardslimited",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isstandardslimitededitable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isusingpercentforstndautocalc",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
