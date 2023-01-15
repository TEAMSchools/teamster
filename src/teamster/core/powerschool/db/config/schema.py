from dagster import Array, Bool, Field, Int, ScalarUnion, Shape, String

AVRO_TYPES = {
    "DB_TYPE_CHAR": ["null", "bytes", "string"],
    "DB_TYPE_NCHAR": ["null", "bytes", "string"],
    "DB_TYPE_VARCHAR": ["null", "bytes", "string"],
    "DB_TYPE_NVARCHAR": ["null", "bytes", "string"],
    "DB_TYPE_RAW": ["null", "bytes", "string"],
    "DB_TYPE_LONG": ["null", "bytes", "string"],
    "DB_TYPE_LONG_RAW": ["null", "bytes", "string"],
    "DB_TYPE_ROWID": ["null", "bytes", "string"],
    "DB_TYPE_UROWID": ["null", "bytes", "string"],
    "DB_TYPE_CLOB": ["null", "bytes", "string"],
    "DB_TYPE_NCLOB": ["null", "bytes", "string"],
    "DB_TYPE_BLOB": ["null", "bytes", "string"],
    "DB_TYPE_NUMBER": ["null", "boolean", "int", "float", "long", "double"],
    "DB_TYPE_BINARY_INTEGER": ["null", "boolean", "int", "float", "long", "double"],
    "DB_TYPE_BINARY_FLOAT": ["null", "boolean", "int", "float", "long", "double"],
    "DB_TYPE_BINARY_DOUBLE": ["null", "boolean", "int", "float", "long", "double"],
    "DB_TYPE_BOOLEAN": ["null", "boolean"],
    "DB_TYPE_DATE": ["null", "string"],
    "DB_TYPE_TIMESTAMP": ["null", "string"],
    "DB_TYPE_TIMESTAMP_TZ": ["null", "string"],
    "DB_TYPE_TIMESTAMP_LTZ": ["null", "string"],
    "DB_TYPE_INTERVAL_YM": ["null"],
    "DB_TYPE_INTERVAL_DS": ["null"],
    "DB_TYPE_BFILE": ["null"],
    "DB_TYPE_JSON": ["null"],
    "DB_TYPE_CURSOR": ["null"],
    "DB_TYPE_OBJECT": ["null"],
}

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

TABLES_CONFIG = Shape(
    {
        "queries": Field(Array(QUERY_CONFIG)),
        "graph_alias": Field(String),
        "resync": Field(Bool, is_required=False, default_value=False),
    }
)
