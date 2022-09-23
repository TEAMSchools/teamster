from dagster import Array, Field, Int, IntSource, Selector, Shape, String, StringSource

SSH_TUNNEL_CONFIG = Shape(
    {
        "remote_port": IntSource,
        "remote_host": Field(StringSource, is_required=False),
        "local_port": Field(IntSource, is_required=False),
    }
)

PS_DB_CONFIG = Shape(
    {
        "ssh_tunnel": Field(SSH_TUNNEL_CONFIG, is_required=False),
        "partition_size": Field(Int, is_required=False, default_value=10000),
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
