# does not work everywhere due to IP filter

from dagster import EnvVar, materialize
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.kipptaf.ldap.assets import build_ldap_asset
from teamster.kipptaf.ldap.resources import LdapResource


def _test_ldap_asset(name, search_base, search_filter):
    asset = build_ldap_asset(
        name=name, search_base=search_base, search_filter=search_filter
    )

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": GCSIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME),
                gcs_bucket="teamster-staging",
                object_type="avro",
            ),
            "ldap": LdapResource(
                host="204.8.89.213",
                port=636,
                user=EnvVar("LDAP_USER"),
                password=EnvVar("LDAP_PASSWORD"),
            ),
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]
        .value
        > 0
    )


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
