from dagster import Array, Field, Permissive, Selector, Shape, String

COMPOSE_QUERIES_CONFIG = Shape(
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
                    "file": Shape(
                        {
                            "stem": String,
                            "suffix": String,
                            "format": Field(Permissive({}), is_required=False),
                        }
                    ),
                }
            )
        ),
    }
)
