import time

from dagster import EnvVar, build_resources

from teamster.libraries.zendesk.resources import ZendeskResource


def build_zendesk_resource() -> ZendeskResource:
    with build_resources(
        {
            "zendesk": ZendeskResource(
                subdomain=EnvVar("ZENDESK_SUBDOMAIN"),
                email=EnvVar("ZENDESK_EMAIL"),
                token=EnvVar("ZENDESK_TOKEN"),
            )
        }
    ) as resources:
        return resources.zendesk


def test_zendesk_create_user():
    zendesk = build_zendesk_resource()

    post_response = zendesk.post(
        resource="users", json={"user": {"name": "Python Test"}}
    ).json()
    print(post_response)

    delete_response = zendesk.delete(
        resource="users", id=post_response["user"]["id"]
    ).json()
    print(delete_response)


def test_zendesk_delete_user():
    zendesk = build_zendesk_resource()

    response = zendesk.delete(resource="users", id=32136419671831).json()
    print(response)


def test_zendesk_list_users():
    zendesk = build_zendesk_resource()

    response = zendesk.list(resource="users")
    print(response[0])


def test_zendesk_show_user():
    zendesk = build_zendesk_resource()

    response = zendesk.get(resource="users", id=32149551391511).json()
    print(response)


def test_zendesk_update_user():
    zendesk = build_zendesk_resource()

    response = zendesk.put(
        resource="users",
        id=187173662,
        json={
            "user": {
                "organization_id": None,
                "user_fields": {"secondary_location": None},
            }
        },
    ).json()
    print(response)


def test_zendesk_create_or_update_many():
    zendesk = build_zendesk_resource()

    payload = {"users": []}

    response = zendesk.post(resource="users/create_or_update_many", json=payload).json()
    print(response)

    while response["job_status"]["status"] != "completed":
        response = zendesk.get(
            resource="job_statuses", id=response["job_status"]["id"]
        ).json()
        print(response)

        time.sleep(1.0)


"""
[
    {"id": 32149551391511, "email": "python_test_1@kippteamandfamily.org"},
    {"id": 32149551391383, "email": "python_test_2@gmail.com"},
    {"id": 32149551391255, "email": "python_test_3@kippteamandfamily.org"},
    {"id": 32149551391127, "email": "python_test_4@apps.teamschools.org"},
]
"""
