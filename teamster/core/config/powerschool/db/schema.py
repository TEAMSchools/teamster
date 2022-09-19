from dagster import (
    Array,
    Enum,
    EnumValue,
    Field,
    IntSource,
    Permissive,
    Selector,
    Shape,
    String,
    StringSource,
)

SSH_TUNNEL_CONFIG = Shape(
    {
        "remote_port": IntSource,
        "remote_host": Field(StringSource, is_required=False),
        "local_port": Field(IntSource, is_required=False),
    }
)

QUERY_CONFIG = Shape(
    {
        "ssh_tunnel": Field(SSH_TUNNEL_CONFIG, is_required=False),
        "output_fmt": Field(String, is_required=False, default_value="dict"),
        "sql": Selector(
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
                                Array(String),
                                default_value=["*"],
                                is_required=False,
                            ),
                            "where": Field(String, is_required=False),
                        }
                    )
                ),
            }
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

DESTINATION_CONFIG = Shape(
    {
        "type": Field(
            Enum(
                name="DestinationType",
                enum_values=[EnumValue("sftp"), EnumValue("gsheet"), EnumValue("file")],
            )
        ),
        "name": Field(String, is_required=False),
        "path": Field(String, is_required=False),
    }
)

PS_DB_CONFIG = {
    "query": Field(QUERY_CONFIG),
    "file": Field(DATA_FILE_CONFIG, is_required=False),
    "destination": Field(DESTINATION_CONFIG),
}
