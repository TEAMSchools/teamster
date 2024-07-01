from dagster import EnvVar, build_resources

from teamster.libraries.tableau.resources import TableauServerResource

with build_resources(
    resources={
        "tableau": TableauServerResource(
            server_address=EnvVar("TABLEAU_SERVER_ADDRESS"),
            site_id=EnvVar("TABLEAU_SITE_ID"),
            token_name=EnvVar("TABLEAU_TOKEN_NAME"),
            personal_access_token=EnvVar("TABLEAU_PERSONAL_ACCESS_TOKEN"),
        )
    }
) as resources:
    TABLEAU_SERVER_RESOURCE: TableauServerResource = resources.tableau
