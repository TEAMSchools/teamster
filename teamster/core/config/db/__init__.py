from dagster import (
    Array,
    Field,
    IntSource,
    Permissive,
    Selector,
    Shape,
    String,
    StringSource,
)

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
                                        Array(String),
                                        default_value=["*"],
                                        is_required=False,
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
            "remote_port": IntSource,
            "remote_host": Field(StringSource, is_required=False),
            "local_port": Field(IntSource, is_required=False),
        }
    ),
    is_required=False,
)
