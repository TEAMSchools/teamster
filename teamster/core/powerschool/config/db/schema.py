from dagster import Array, Field, Int, ScalarUnion, Shape, String

QUERY_CONFIG = Shape(
    {
        "partition_size": Field(Int, is_required=False, default_value=100000),
        "sql": Shape(
            {
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
                            "where": Field(
                                ScalarUnion(
                                    scalar_type=String,
                                    non_scalar_schema=Shape(
                                        {
                                            "column": Field(String),
                                            "value": Field(
                                                String,
                                                is_required=False,
                                                default_value="last_run",
                                            ),
                                        }
                                    ),
                                ),
                                is_required=False,
                            ),
                        }
                    )
                ),
            }
        ),
    }
)

TABLES_CONFIG = Field(Shape({"queries": Array(QUERY_CONFIG)}), is_required=False)
