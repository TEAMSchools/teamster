from teamster.core.datagun.assets import sftp_extract_asset_factory

students_accessaccounts = sftp_extract_asset_factory(
    asset_name="students_accessaccounts",
    query_config={
        "query_type": "schema",
        "query_value": {
            "table": {
                "name": "powerschool_autocomm_students_accessaccounts",
                "schema": "extracts",
            },
            "where": "db_name = 'kippnewark'",
        },
    },
    file_config={
        "stem": "powerschool_autocomm_students_accessaccounts",
        "suffix": "txt",
        "format": {"header": False, "sep": "\t"},
    },
    destination_config={
        "name": "pythonanywhere",
        "path": "sftp/powerschool/kippnewark",
    },
)
