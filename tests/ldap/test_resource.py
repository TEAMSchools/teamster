import pickle

from dagster import EnvVar, build_resources

from teamster.core.ldap.resources import LdapResource

SEARCH_BASE = "dc=teamschools,dc=kipp,dc=org"
SEARCH_FILTERS = ["(&(objectClass=user)(objectCategory=person))", "(objectClass=group)"]

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
            )

            entries = []
            for entry in ldap._connection.entries:
                entries.append(
                    {
                        key: values if key in ARRAY_ATTRIBUTES else values[0]
                        for key, values in entry.entry_attributes_as_dict.items()
                    }
                )

            with open(file=f"env/{search_filter}.pickle", mode="wb") as f:
                pickle.dump(obj=entries, file=f)
