from dagster import Array, Enum, EnumValue, Field, Permissive, Selector, Shape, String

DESTINATION_CONFIG = Shape(
    {
        "type": Field(
            Enum(
                name="DestinationType",
                enum_values=[EnumValue("sftp"), EnumValue("gsheet"), EnumValue("fs")],
            )
        ),
        "name": Field(String, is_required=False),
        "path": Field(String, is_required=False),
    }
)

SQL_CONFIG = Selector(
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

DATA_FILE_CONFIG = Shape(
    {
        "stem": Field(String),
        "suffix": Field(String),
        "format": Field(Permissive(), is_required=False),
    }
)

QUERY_CONFIG = Field(
    Shape(
        {
            "destination": Field(DESTINATION_CONFIG),
            "queries": Field(
                Array(
                    Shape(
                        {
                            "sql": Field(SQL_CONFIG),
                            "output_fmt": Field(String),
                            "file": Field(DATA_FILE_CONFIG, is_required=False),
                        }
                    )
                )
            ),
        }
    )
)
