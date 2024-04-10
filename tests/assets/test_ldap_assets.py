from dagster import materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.resources import LDAP_RESOURCE


def _test_ldap_asset(asset):
    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "ldap": LDAP_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # type: ignore
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""


""" does not work in dev: IP filter
def test_asset_ldap_user_person():
    _test_ldap_asset(
        name="user_person",
        search_base="dc=teamschools,dc=kipp,dc=org",
        search_filter="(&(objectClass=user)(objectCategory=person))",
    )


def test_asset_ldap_group():
    _test_ldap_asset(
        name="group",
        search_base="dc=teamschools,dc=kipp,dc=org",
        search_filter="(objectClass=group)",
    )
"""
