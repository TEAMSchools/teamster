import pickle

from dagster import EnvVar, build_resources

from teamster.core.ldap.resources import LdapResource

SEARCH_BASE = "dc=teamschools,dc=kipp,dc=org"
SEARCH_FILTERS = [
    "(&(whenChanged>=20230629000000.000000-0500)(&(objectClass=user)(objectCategory=person)))",
    # "(&(objectClass=user)(objectCategory=person))",
    # "(objectClass=group)",
]

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


def test_resource():
    with build_resources(
        {
            "ldap": LdapResource(
                host="ldap1.kippnj.org",
                port=636,
                user=EnvVar("LDAP_USER"),
                password=EnvVar("LDAP_PASSWORD"),
            )
        }
    ) as resources:
        ldap: LdapResource = resources.ldap
        # print(ldap._connection)

        for search_filter in SEARCH_FILTERS:
            ldap._connection.search(
                search_base=SEARCH_BASE,
                search_filter=search_filter,
                attributes=["*"],
                size_limit=1,
            )
            # print(ldap._connection)

            entries = []
            for entry in ldap._connection.entries:
                primitive_items = {
                    key: values[0]
                    if key not in DATETIME_ATTRIBUTES
                    else values[0].timestamp()
                    for key, values in entry.entry_attributes_as_dict.items()
                }

                array_items = {
                    key: values
                    for key, values in entry.entry_attributes_as_dict.items()
                    if key in ARRAY_ATTRIBUTES
                }

                entries.append({**primitive_items, **array_items})
            print(len(entries))
            print(entries[0])

            # with open(file=f"env/{search_filter}.pickle", mode="wb") as f:
            #     pickle.dump(obj=entries, file=f)
