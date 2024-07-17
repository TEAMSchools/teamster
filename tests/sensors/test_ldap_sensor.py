from teamster.code_locations.kipptaf.resources import LDAP_RESOURCE

SEARCH_BASE = "dc=teamschools,dc=kipp,dc=org"
TESTS = [
    {
        "search_filter": "(&(objectClass=user)(objectCategory=person))",
        "whenChanged": "20230629000000.000000-0500",
    }
]


def _test():
    for test in TESTS:
        when_changed = test["whenChanged"]
        search_filter = test["search_filter"]

        LDAP_RESOURCE._connection.search(
            search_base=SEARCH_BASE,
            search_filter=(
                f"(&(idautoChallengeSetTimestamp>={when_changed}){search_filter})"
            ),
            # size_limit=1,
        )

        print(len(LDAP_RESOURCE._connection.entries))
        print(LDAP_RESOURCE._connection.entries)
