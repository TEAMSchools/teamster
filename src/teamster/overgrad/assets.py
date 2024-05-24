from dagster import AssetExecutionContext, Output, asset

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)
from teamster.overgrad.resources import OvergradResource
from teamster.overgrad.schema import (
    ADMISSION_SCHEMA,
    CUSTOM_FIELD_SCHEMA,
    FOLLOWING_SCHEMA,
    SCHOOL_SCHEMA,
    STUDENT_SCHEMA,
    UNIVERSITY_SCHEMA,
)


def build_overgrad_asset(endpoint, schema):
    @asset(
        key=["overgrad", endpoint],
        io_manager_key="io_manager_gcs_avro",
        group_name="overgrad",
        check_specs=[get_avro_schema_valid_check_spec(["overgrad", endpoint])],
    )
    def _asset(context: AssetExecutionContext, overgrad: OvergradResource):
        data = overgrad.get_list(path=endpoint)

        import json
        import pathlib

        fp = pathlib.Path(f"env/overgrad/{endpoint}.json")
        fp.parent.mkdir(parents=True, exist_ok=True)
        json.dump(obj=data, fp=fp.open("w"))

        yield Output(value=(data, schema), metadata={"row_count": len(data)})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset


admissions = build_overgrad_asset(endpoint="admissions", schema=ADMISSION_SCHEMA)
followings = build_overgrad_asset(endpoint="followings", schema=FOLLOWING_SCHEMA)
schools = build_overgrad_asset(endpoint="schools", schema=SCHOOL_SCHEMA)
students = build_overgrad_asset(endpoint="students", schema=STUDENT_SCHEMA)
universities = build_overgrad_asset(endpoint="universities", schema=UNIVERSITY_SCHEMA)
custom_fields = build_overgrad_asset(
    endpoint="custom_fields", schema=CUSTOM_FIELD_SCHEMA
)

assets = [
    admissions,
    custom_fields,
    followings,
    schools,
    students,
    universities,
]
