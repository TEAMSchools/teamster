from teamster.core.datagun.assets import gsheet_extract_asset_factory

test = gsheet_extract_asset_factory(
    asset_name="test",
    key_prefix="gsheet",
    query_config={
        "query_type": "text",
        "query_value": (
            "SELECT "
            "n AS n0, n + 1 AS n1, n + 2 AS n2, n + 3 AS n3, n + 4 AS n4 "
            "FROM utilities.row_generator_smallint "
            "WHERE n <= 5"
        ),
    },
    file_config={"stem": "test", "suffix": "gsheet"},
)
