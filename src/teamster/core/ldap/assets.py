from dagster import AssetExecutionContext, Output, asset

from teamster.core.ldap.resources import LdapResource
from teamster.core.ldap.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

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
    name, code_location, search_base, search_filter, attributes=["*"], op_tags={}
):
    @asset(
        name=name,
        key_prefix=[code_location, "ldap"],
        metadata={
            "search_base": search_base,
            "search_filter": search_filter,
            "attributes": attributes,
        },
        io_manager_key="gcs_avro_io",
        op_tags=op_tags,
    )
    def _asset(context: AssetExecutionContext, ldap: LdapResource):
        asset_name = context.assets_def.key.path[-1]
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]

        ldap._connection.search(
            search_base=asset_metadata["search_base"],
            search_filter=asset_metadata["search_filter"],
            attributes=asset_metadata["attributes"],
        )

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
            value=(
                entries,
                get_avro_record_schema(
                    name=asset_name, fields=ASSET_FIELDS[asset_name]
                ),
            ),
            metadata={"records": len(entries)},
        )

    return _asset
