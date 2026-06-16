import json

from dagster import AssetExecutionContext, AssetsDefinition, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.finalsite.api.resources import FinalsiteResource


def build_finalsite_asset(code_location: str, asset_name: str, schema):
    key = [code_location, "finalsite", asset_name]

    @asset(
        key=key,
        io_manager_key="io_manager_gcs_avro",
        # partitions_def=partitions_def,
        check_specs=[build_check_spec_avro_schema_valid(key)],
        group_name="finalsite",
        kinds={"python"},
    )
    def _asset(context: AssetExecutionContext, finalsite: FinalsiteResource):
        data = finalsite.list(path=asset_name)

        yield Output(value=(data, schema), metadata={"record_count": len(data)})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset


def _coerce_attr_values(record: dict) -> dict:
    """Stringify custom/track/id attribute values (lists -> JSON) in place.

    A multi-type Avro union for the attribute ``value`` field loads poorly into a
    BigQuery external table, so the asset narrows every value to a string before
    the Avro write. Recurses into expanded guardian contacts under
    ``relationships[].contact``.
    """
    for key in ("custom_attributes", "track_attributes", "id_attributes"):
        for attr in record.get(key) or []:
            value = attr.get("value")
            if value is None or isinstance(value, str):
                continue
            attr["value"] = json.dumps(value) if isinstance(value, list) else str(value)

    for rel in record.get("relationships") or []:
        contact = rel.get("contact")
        if contact:
            _coerce_attr_values(contact)

    return record


def build_finalsite_contacts_asset(
    code_location: str, schema: dict
) -> AssetsDefinition:
    key = [code_location, "finalsite", "contacts"]

    @asset(
        key=key,
        io_manager_key="io_manager_gcs_avro",
        check_specs=[build_check_spec_avro_schema_valid(key)],
        group_name="finalsite",
        kinds={"python"},
    )
    def _asset(context: AssetExecutionContext, finalsite: FinalsiteResource):
        school_years = finalsite.get(path="school_years").json().get("school_years", [])

        data: list[dict] = []
        chosen_year = None
        for year in sorted(
            school_years, key=lambda y: y.get("start_year") or 0, reverse=True
        ):
            data = finalsite.list(
                path="contacts",
                params={
                    "school_year_id": year.get("id"),
                    "count": 25,
                    "includes": "contacts.relationships.contact",
                },
            )
            if data:
                chosen_year = year
                break

        data = [_coerce_attr_values(record) for record in data]

        context.log.info(
            f"school_year start={chosen_year.get('start_year') if chosen_year else None}; "
            f"contacts={len(data)}"
        )

        yield Output(value=(data, schema), metadata={"record_count": len(data)})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
