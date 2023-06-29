from dagster import EnvVar, build_resources

from teamster.core.ldap.resources import LdapResource

SEARCH_BASE = "dc=teamschools,dc=kipp,dc=org"
TESTS = [
    {
        "search_filter": "(&(objectClass=user)(objectCategory=person))",
        "whenChanged": "20230629000000.000000-0500",
    }
]


def test_sensor():
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

        for test in TESTS:
            when_changed = test["whenChanged"]
            search_filter = test["search_filter"]

            ldap._connection.search(
                search_base=SEARCH_BASE,
                search_filter=(
                    f"(&(idautoChallengeSetTimestamp>={when_changed}){search_filter})"
                ),
                # size_limit=1,
            )

            print(len(ldap._connection.entries))
            print(ldap._connection.entries)
