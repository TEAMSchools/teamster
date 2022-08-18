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

QUERY_DESTINATION_CONFIG = Field(
    Shape(
        {
            "type": Field(String),
            "name": Field(String, is_required=False),
            "path": Field(String, is_required=False),
        }
    )
)

QUERY_SQL_CONFIG = Field(
    Selector(
        {
            "text": Field(String),
            "file": Field(String),
            "schema": Field(
                Shape(
                    {
                        "table": Field(
                            Shape(
                                {
                                    "name": Field(String),
                                    "schema": Field(String, is_required=False),
                                }
                            )
                        ),
                        "select": Field(
                            Array(String), default_value=["*"], is_required=False
                        ),
                        "where": Field(String, is_required=False),
                    }
                )
            ),
        }
    )
)

QUERY_FILE_CONFIG = Field(
    Shape(
        {
            "stem": Field(String),
            "suffix": Field(String),
            "format": Field(Permissive({}), is_required=False),
        }
    ),
    is_required=False,
)

QUERY_CONFIG = Field(
    Shape(
        {
            "destination": QUERY_DESTINATION_CONFIG,
            "queries": Field(
                Array(Shape({"sql": QUERY_SQL_CONFIG, "file": QUERY_FILE_CONFIG}))
            ),
        }
    )
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
