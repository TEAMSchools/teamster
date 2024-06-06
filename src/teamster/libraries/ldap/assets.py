from dagster import AssetExecutionContext, Output, asset

from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.ldap.resources import LdapResource

# via http://www.phpldaptools.com/reference/Default-Schema-Attributes
ARRAY_ATTRIBUTES = [
    "member",
    "memberOf",
    "otherFacsimileTelephoneNumber",
    "otherHomePhone",
    "otherIpPhone",
    "otherPager",
    "otherTelephoneNumber",
    "proxyAddresses",
    "publicDelegates",
    "servicePrincipalName",
    "userWorkstations",
]

DATETIME_ATTRIBUTES = [
    "accountExpires",
    "badPasswordTime",
    "dSCorePropagationData",
    "idautoChallengeSetTimestamp",
    "idautoGroupLastSynced",
    "idautoPersonEndDate",
    "lastLogoff",
    "lastLogon",
    "lastLogonTimestamp",
    "lockoutTime",
    "msExchWhenMailboxCreated",
    "msTSExpireDate",
    "pwdLastSet",
    "whenChanged",
    "whenCreated",
]


def build_ldap_asset(
    asset_key,
    search_base,
    search_filter,
    schema,
    attributes: list | None = None,
    op_tags: dict | None = None,
):
    if attributes is None:
        attributes = ["*"]

    if op_tags is None:
        op_tags = {}

    @asset(
        key=asset_key,
        metadata={
            "search_base": search_base,
            "search_filter": search_filter,
            "attributes": attributes,
        },
        io_manager_key="io_manager_gcs_avro",
        op_tags=op_tags,
        group_name="ldap",
        compute_kind="python",
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, ldap: LdapResource):
        ldap._connection.search(**context.assets_def.metadata_by_key[context.asset_key])

        entries = []
        for entry in ldap._connection.entries:
            primitive_items = {
                key.replace("-", "_"): values[0]
                if key not in DATETIME_ATTRIBUTES
                else values[0].timestamp()
                for key, values in entry.entry_attributes_as_dict.items()
            }

            array_items = {
                key.replace("-", "_"): values
                for key, values in entry.entry_attributes_as_dict.items()
                if key in ARRAY_ATTRIBUTES
            }

            entries.append({**primitive_items, **array_items})

        yield Output(
            value=(entries, schema),
            metadata={"records": len(entries)},
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=entries, schema=schema
        )

    return _asset
