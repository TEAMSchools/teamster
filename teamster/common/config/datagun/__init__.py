from dagster import Array, Field, Permissive, Selector, Shape, String

DB_QUERY_CONFIG = Shape(
    {
        "destination": Shape(
            {"name": String, "type": String, "path": Field(String, is_required=False)}
        ),
        "queries": Array(
            Shape(
                {
                    "sql": Selector(
                        {
                            "text": String,
                            "file": String,
                            "schema": Shape(
                                {
                                    "table": String,
                                    "columns": Field(
                                        String,
                                        is_required=False,
                                        default_value="*",
                                    ),
                                    "where": Field(String, is_required=False),
                                }
                            ),
                        }
                    ),
                    "file": Field(
                        Shape(
                            {
                                "stem": Field(String, is_required=False),
                                "suffix": Field(String, is_required=False),
                                "format": Field(Permissive({}), is_required=False),
                            }
                        ),
                        is_required=False,
                    ),
                }
            )
        ),
    }
)
