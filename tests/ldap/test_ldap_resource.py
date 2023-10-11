import pickle

from dagster import EnvVar, build_resources

from teamster.core.ldap.resources import LdapResource

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


def _test(search_filter):
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

    ldap._connection.search(
        search_base="dc=teamschools,dc=kipp,dc=org",
        search_filter=search_filter,
        attributes=["*"],
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

    with open(file=f"env/{search_filter}.pickle", mode="wb") as f:
        pickle.dump(obj=entries, file=f)


def test_user_person():
    _test(
        "(&(whenChanged>=20230628000000.000000-0500)(&(objectClass=user)(objectCategory=person)))"
    )


def test_group():
    _test("(objectClass=group)")
