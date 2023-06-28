from dagster import EnvVar, build_resources

from teamster.core.ldap.resources import LdapResource


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

        print(ldap._connection)
        print(ldap._connection.extend.standard.who_am_i())
