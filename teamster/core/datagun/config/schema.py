from dagster import (
    Array,
    Enum,
    EnumValue,
    Field,
    Int,
    IntSource,
    Permissive,
    Selector,
    Shape,
    String,
    StringSource,
)

DESTINATION_CONFIG = Shape(
    {
        "type": Field(
            Enum(
                name="DestinationType",
                enum_values=[EnumValue("sftp"), EnumValue("gsheet")],
            )
        ),
        "name": Field(String, is_required=False),
        "path": Field(String, is_required=False),
    }
)

FILE_CONFIG = Shape(
    {
        "stem": Field(String, is_required=False, default_value="{now}"),
        "suffix": Field(String, is_required=False, default_value="json.gz"),
        "encoding": Field(String, is_required=False, default_value="utf-8"),
        "format": Field(Permissive(), is_required=False, default_value={}),
    }
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
        "partition_size": Field(Int, is_required=False, default_value=100000),
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

DATAGUN_CONFIG = Shape(
    {
        "query": Field(QUERY_CONFIG),
        "file": Field(FILE_CONFIG, is_required=False),
        "destination": Field(DESTINATION_CONFIG),
    }
)
