"""Resource credential fields stay out of ``repr``.

A failing test's traceback prints ``self = <Resource>(...)``; before #5116 that
frame showed live credentials.
"""

import pytest

from teamster.libraries.adp.workforce_manager.resources import (
    AdpWorkforceManagerResource,
)
from teamster.libraries.adp.workforce_now.api.resources import (
    AdpWorkforceNowResource,
)
from teamster.libraries.amplify.dibels.resources import DibelsDataSystemResource
from teamster.libraries.amplify.mclass.api.resources import MClassResource
from teamster.libraries.couchdrop.resources import CouchdropResource
from teamster.libraries.coupa.resources import CoupaResource
from teamster.libraries.dlt.powerschool.resources import OracleResource
from teamster.libraries.email.resources import EmailResource
from teamster.libraries.finalsite.api.resources import FinalsiteResource
from teamster.libraries.knowbe4.resources import KnowBe4Resource
from teamster.libraries.ldap.resources import LdapResource
from teamster.libraries.level_data.grow.resources import GrowResource
from teamster.libraries.overgrad.resources import OvergradResource
from teamster.libraries.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)
from teamster.libraries.powerschool.sis.odbc.resources import (
    PowerSchoolODBCResource,
)
from teamster.libraries.smartrecruiters.resources import SmartRecruitersResource
from teamster.libraries.ssh.resources import SSHResource
from teamster.libraries.tableau.resources import TableauServerResource
from teamster.libraries.zendesk.resources import ZendeskResource

HIDDEN_FIELDS = [
    (AdpWorkforceManagerResource, "app_key"),
    (AdpWorkforceManagerResource, "client_id"),
    (AdpWorkforceManagerResource, "client_secret"),
    (AdpWorkforceManagerResource, "password"),
    (AdpWorkforceNowResource, "client_id"),
    (AdpWorkforceNowResource, "client_secret"),
    (DibelsDataSystemResource, "password"),
    (MClassResource, "password"),
    (CouchdropResource, "password"),
    (CoupaResource, "client_id"),
    (CoupaResource, "client_secret"),
    (OracleResource, "password"),
    (EmailResource, "password"),
    (FinalsiteResource, "credential_id"),
    (FinalsiteResource, "secret"),
    (KnowBe4Resource, "api_key"),
    (LdapResource, "password"),
    (GrowResource, "client_id"),
    (GrowResource, "client_secret"),
    (OvergradResource, "api_key"),
    (PowerSchoolEnrollmentResource, "api_key"),
    (PowerSchoolODBCResource, "password"),
    (SmartRecruitersResource, "smart_token"),
    (SSHResource, "password"),
    (SSHResource, "key_string"),
    (TableauServerResource, "personal_access_token"),
    (ZendeskResource, "client_id"),
    (ZendeskResource, "client_secret"),
]


@pytest.mark.parametrize(
    ("cls", "field"), HIDDEN_FIELDS, ids=lambda x: getattr(x, "__name__", x)
)
def test_credential_field_hidden_from_repr(cls, field: str):
    assert cls.model_fields[field].repr is False


def test_repr_omits_credential_values():
    """End to end on an own field and on one redeclared over an upstream parent."""
    grow = GrowResource(
        client_id="dummy-client-id", client_secret="dummy-secret", district_id="x"
    )
    ssh = SSHResource(remote_host="h", username="u", password="dummy-pw")

    for text in (repr(grow), str(grow), repr(ssh), str(ssh)):
        for value in ("dummy-client-id", "dummy-secret", "dummy-pw"):
            assert value not in text
