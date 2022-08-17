from dagster import Array, Field, Int, Permissive, Selector, Shape, String

QUERY_CONFIG = Shape(
    {
        "destination": Shape(
            {
                "type": String,
                "name": Field(String, is_required=False),
                "path": Field(String, is_required=False),
            }
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

SSH_TUNNEL_CONFIG = Field(
    Shape(
        {
            "remote_port": Int,
            "remote_host": Field(String, is_required=False),
            "local_port": Field(Int, is_required=False),
        }
    ),
    is_required=False,
)
