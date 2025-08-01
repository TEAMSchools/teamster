from dagster import AssetCheckResult, AssetCheckSeverity, AssetCheckSpec, MetadataValue


def build_check_spec_avro_schema_valid(asset):
    return AssetCheckSpec(
        name="avro_schema_valid",
        asset=asset,
        description=(
            "Checks output records against the supplied schema and warns if any "
            "unexpected fields are discovered"
        ),
    )


def check_avro_schema_valid(asset_key, records, schema):
    record_fields = set().union(
        [k for r in records for k in r.keys() if not k[0].isdigit()]
    )
    schema_fields = set(field["name"] for field in schema["fields"])

    extras = record_fields - schema_fields

    return AssetCheckResult(
        passed=len(extras) == 0,
        asset_key=asset_key,
        check_name="avro_schema_valid",
        metadata={"extras": MetadataValue.text(", ".join(extras))},
        severity=AssetCheckSeverity.WARN,
    )
