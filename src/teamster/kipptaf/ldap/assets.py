from dagster import AssetExecutionContext, Output, asset, config_from_files

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_record_schema,
    get_avro_schema_valid_check_spec,
)

from .. import CODE_LOCATION
from .resources import LdapResource
from .schema import ASSET_FIELDS

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


def build_ldap_asset(name, search_base, search_filter, attributes=["*"], op_tags={}):
    asset_key = [CODE_LOCATION, "ldap", name]

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
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(context: AssetExecutionContext, ldap: LdapResource):
        asset_name = context.asset_key.path[-1]

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

        schema = get_avro_record_schema(
            name=asset_name, fields=ASSET_FIELDS[asset_name]
        )

        yield Output(
            value=(entries, schema),
            metadata={"records": len(entries)},
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=entries, schema=schema
        )

    return _asset


ldap_assets = [
    build_ldap_asset(**asset)
    for asset in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/ldap/config/assets.yaml"]
    )["assets"]
]

__all__ = [
    *ldap_assets,
]
