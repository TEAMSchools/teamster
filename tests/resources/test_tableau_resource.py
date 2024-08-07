from dagster import EnvVar, build_init_resource_context, build_resources

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
    tableau: TableauServerResource = resources.tableau


def test_tableau_workbook_refresh():
    tableau.setup_for_execution(context=build_init_resource_context())

    workbook = tableau._server.workbooks.get_by_id(
        "7adabf6e-fa59-4d60-bca8-de3a67005a53"
    )

    tableau._server.workbooks.refresh(workbook)
