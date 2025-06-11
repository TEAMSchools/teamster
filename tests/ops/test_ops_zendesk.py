from dagster import build_op_context

from teamster.libraries.zendesk.ops import zendesk_user_sync_op


def test_zendesk_user_sync_op():
    from teamster.core.resources import ZENDESK_RESOURCE

    users = [
        {
            "email": "python_test_1@kippnj.org",
            "external_id": "9999991",
            "name": "Python Test 1",
            "suspended": False,
            "role": "end-user",
            "organization_id": 360037335133,
            "user_fields": {"secondary_location": "room_9"},
            "identities": [
                {"type": "email", "value": "python_test_1@kippteamandfamily.org"},
                {"type": "email", "value": "python_test_1@gmail.com"},
                {"type": "google", "value": "python_test_1@apps.teamschools.org"},
            ],
        },
        {
            "email": "python_test_2@kippteamandfamily.org",
            "external_id": "9999992",
            "name": "Python Test 2",
            "suspended": False,
            "role": "end-user",
            "organization_id": 360037335133,
            "identities": [
                {"type": "email", "value": "python_test_2@gmail.com"},
                {"type": "google", "value": "python_test_2@apps.teamschools.org"},
                # TEST: additional user identity matches existing primary email
                # {"type": "email", "value": "python_test_1@kippnj.org"},
                # TEST: additional user identity matches existing additional identity
                # {"type": "email", "value": "python_test_1@kippteamandfamily.org"},
            ],
        },
        {
            "email": "python_test_3@kippmiami.org",
            "external_id": "9999993",
            "name": "Python Test 3",
            "suspended": False,
            "role": "end-user",
            "organization_id": 360037335133,
            "identities": [
                {"type": "email", "value": "python_test_3@kippteamandfamily.org"},
                {"type": "email", "value": "python_test_3@gmail.com"},
                {"type": "google", "value": "python_test_3@kippmiami.org"},
            ],
        },
        {
            "email": "python_test_4@kippmiami.org",
            "external_id": "9999994",
            "name": "Python Test 4",
            "suspended": True,
            "role": "end-user",
            "organization_id": 360037335133,
            "identities": [
                {"type": "google", "value": "python_test_4@apps.teamschools.org"}
            ],
        },
    ]

    with build_op_context() as context:
        output = zendesk_user_sync_op(
            context=context, zendesk=ZENDESK_RESOURCE, users=users
        )

    for o in output:
        context.log.info(o)
