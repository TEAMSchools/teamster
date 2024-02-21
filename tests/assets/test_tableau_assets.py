from tableauserverclient import (
    Filter,
    Pager,
    PersonalAccessTokenAuth,
    RequestOptions,
    Server,
)

server = Server(server_address="https://tableau.kipp.org", use_server_version=True)
tableau_auth = PersonalAccessTokenAuth(
    token_name="Dagster",
    personal_access_token="",
    site_id="KIPPNJ",
)

server.auth.sign_in(tableau_auth)

req_option = RequestOptions()
req_option.filter.add(
    Filter(
        field=RequestOptions.Field.ProjectName,
        operator=RequestOptions.Operator.Equals,
        value="Production",
    )
)

all_workbooks = list(Pager(endpoint=server.workbooks, request_opts=req_option))

for workbook in all_workbooks:
    print(f"{workbook.updated_at} {workbook.id} {workbook.name}")
