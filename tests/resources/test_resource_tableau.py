from dagster import EnvVar, build_init_resource_context, build_resources

from teamster.libraries.tableau.resources import TableauServerResource


def get_tableau_resource():
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

    tableau.setup_for_execution(context=build_init_resource_context())

    return tableau


def test_tableau_workbook_refresh():
    tableau = get_tableau_resource()

    workbook = tableau._server.workbooks.get_by_id(
        "7adabf6e-fa59-4d60-bca8-de3a67005a53"
    )

    tableau._server.workbooks.refresh(workbook)


def test_tableau_get_user():
    from tableauserverclient import Pager

    tableau = get_tableau_resource()

    # print the names of the groups on the server
    for group in Pager(endpoint=tableau._server.users):
        print(group.name, group.id)


def test_tableau_add_group_users():
    from tableauserverclient import Pager

    tableau = get_tableau_resource()

    group_item = [
        group
        for group in Pager(endpoint=tableau._server.groups)
        if group.name == "Teacher Gradebook Email - Auto - Newark"
    ][0]

    users = [
        user
        for user in Pager(endpoint=tableau._server.users)
        if user.email
        in ["cbini@kippteamandfamily.org", "grangel@kippteamandfamily.org"]
    ]

    tableau._server.groups.add_users(group_item=group_item, users=users)
