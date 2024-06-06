from dagster import ConfigurableResource, build_init_resource_context

from teamster.code_locations.kipptaf.resources import (
    ADP_WORKFORCE_MANAGER_RESOURCE,
    ADP_WORKFORCE_NOW_RESOURCE,
    AIRBYTE_CLOUD_RESOURCE,
    ALCHEMER_RESOURCE,
    FIVETRAN_RESOURCE,
    GOOGLE_DIRECTORY_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    GOOGLE_FORMS_RESOURCE,
    GOOGLE_SHEETS_RESOURCE,
    MCLASS_RESOURCE,
    SCHOOLMINT_GROW_RESOURCE,
    SMARTRECRUITERS_RESOURCE,
    SSH_RESOURCE_ADP_WORKFORCE_NOW,
    SSH_RESOURCE_BLISSBOOK,
    SSH_RESOURCE_CLEVER,
    SSH_RESOURCE_COUPA,
    SSH_RESOURCE_DEANSLIST,
    SSH_RESOURCE_EGENCIA,
    SSH_RESOURCE_ILLUMINATE,
    SSH_RESOURCE_LITTLESIS,
    TABLEAU_SERVER_RESOURCE,
    ZENDESK_RESOURCE,
)
from teamster.libraries.core.resources import (  # DB_POWERSCHOOL,; get_ssh_resource_powerschool,
    BIGQUERY_RESOURCE,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    SSH_COUCHDROP,
    SSH_EDPLAN,
    SSH_IREADY,
    SSH_RENLEARN,
    SSH_TITAN,
    get_dbt_cli_resource,
)


def _test_resource_init(resource: ConfigurableResource):
    resource.setup_for_execution(context=build_init_resource_context())


def test_adp_workforce_manager_resource():
    _test_resource_init(ADP_WORKFORCE_MANAGER_RESOURCE)


def test_adp_workforce_now_resource():
    _test_resource_init(ADP_WORKFORCE_NOW_RESOURCE)


def test_airbyte_cloud_resource():
    _test_resource_init(AIRBYTE_CLOUD_RESOURCE)


def test_alchemer_resource():
    _test_resource_init(ALCHEMER_RESOURCE)


def test_bigquery_resource():
    _test_resource_init(BIGQUERY_RESOURCE)


def test_deanslist_resource():
    _test_resource_init(DEANSLIST_RESOURCE)


def test_fivetran_resource():
    _test_resource_init(FIVETRAN_RESOURCE)


def test_gcs_resource():
    _test_resource_init(GCS_RESOURCE)


def test_get_dbt_cli_resource():
    _test_resource_init(get_dbt_cli_resource("staging"))


def test_google_directory_resource():
    _test_resource_init(GOOGLE_DIRECTORY_RESOURCE)


def test_google_drive_resource():
    _test_resource_init(GOOGLE_DRIVE_RESOURCE)


def test_google_forms_resource():
    _test_resource_init(GOOGLE_FORMS_RESOURCE)


def test_google_sheets_resource():
    _test_resource_init(GOOGLE_SHEETS_RESOURCE)


def test_mclass_resource():
    _test_resource_init(MCLASS_RESOURCE)


def test_schoolmint_grow_resource():
    _test_resource_init(SCHOOLMINT_GROW_RESOURCE)


def test_smartrecruiters_resource():
    _test_resource_init(SMARTRECRUITERS_RESOURCE)


def test_ssh_couchdrop():
    _test_resource_init(SSH_COUCHDROP)


def test_ssh_edplan():
    _test_resource_init(SSH_EDPLAN)


def test_ssh_iready():
    _test_resource_init(SSH_IREADY)


def test_ssh_renlearn():
    _test_resource_init(SSH_RENLEARN)


def test_ssh_resource_adp_workforce_now():
    _test_resource_init(SSH_RESOURCE_ADP_WORKFORCE_NOW)


def test_ssh_resource_blissbook():
    _test_resource_init(SSH_RESOURCE_BLISSBOOK)


def test_ssh_resource_clever():
    _test_resource_init(SSH_RESOURCE_CLEVER)


def test_ssh_resource_coupa():
    _test_resource_init(SSH_RESOURCE_COUPA)


def test_ssh_resource_deanslist():
    _test_resource_init(SSH_RESOURCE_DEANSLIST)


def test_ssh_resource_egencia():
    _test_resource_init(SSH_RESOURCE_EGENCIA)


def test_ssh_resource_illuminate():
    _test_resource_init(SSH_RESOURCE_ILLUMINATE)


def test_ssh_resource_littlesis():
    _test_resource_init(SSH_RESOURCE_LITTLESIS)


def test_ssh_titan():
    _test_resource_init(SSH_TITAN)


def test_tableau_server_resource():
    _test_resource_init(TABLEAU_SERVER_RESOURCE)


def test_zendesk_resource():
    _test_resource_init(ZENDESK_RESOURCE)


# def test_db_powerschool():
#     ps_ssh = get_ssh_resource_powerschool("staging")
#     tunnel = ps_ssh.get_tunnel()
#     with tunnel.start():
#         _test_resource_init(DB_POWERSCHOOL)
