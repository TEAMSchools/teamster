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


def test_zendesk_create_or_update_many():
    zendesk = build_zendesk_resource()

    payload = {
        "users": [
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
    }

    response = zendesk.post(resource="users/create_or_update_many", json=payload).json()
    print(response)

    while response["job_status"]["status"] != "completed":
        response = zendesk.get(
            resource="job_statuses", id=response["job_status"]["id"]
        ).json()
        print(response)

        time.sleep(1.0)


# trunk-ignore-all(pyright/reportUnusedExpression)
# trunk-ignore-all(ruff/B018)
# 2025-05-16 16:45:25 +0000 - dagster - DEBUG - resource:zendesk - GET https://teamschools.zendesk.com/api/v2/job_statuses/V3-e39f5612c8dff3465c40c336662ea433
{
    "job_status": {
        "id": "V3-e39f5612c8dff3465c40c336662ea433",
        "job_type": "Bulk Create User",
        "url": "https://teamschools.zendesk.com/api/v2/job_statuses/V3-e39f5612c8dff3465c40c336662ea433.json",
        "total": 4,
        "progress": 4,
        "status": "completed",
        "message": "Completed at 2025-05-16 16:45:25 +0000",
        "results": [
            {
                "id": 32149551391511,
                "status": "Created",
                "email": "python_test_1@kippteamandfamily.org",
                "external_id": "9999991",
            },
            {
                "id": 32149551391383,
                "status": "Created",
                "email": "python_test_2@gmail.com",
                "external_id": "9999992",
            },
            {
                "id": 32149551391255,
                "status": "Created",
                "email": "python_test_3@kippteamandfamily.org",
                "external_id": "9999993",
            },
            {
                "id": 32149551391127,
                "status": "Created",
                "email": "python_test_4@apps.teamschools.org",
                "external_id": "9999994",
            },
        ],
    }
}

# 2025-05-16 16:51:16 +0000 - dagster - DEBUG - resource:zendesk - GET https://teamschools.zendesk.com/api/v2/job_statuses/V3-997c24f6a7fe09d505fd34a5eb24982d
{
    "job_status": {
        "id": "V3-997c24f6a7fe09d505fd34a5eb24982d",
        "job_type": "Bulk Create User",
        "url": "https://teamschools.zendesk.com/api/v2/job_statuses/V3-997c24f6a7fe09d505fd34a5eb24982d.json",
        "total": 4,
        "progress": 4,
        "status": "completed",
        "message": "Completed at 2025-05-16 16:51:15 +0000",
        "results": [
            {
                "id": 32149551391511,
                "status": "Updated",
                "email": "python_test_1@kippteamandfamily.org",
                "external_id": "9999991",
            },
            {
                "id": 32149551391383,
                "status": "Updated",
                "email": "python_test_2@gmail.com",
                "external_id": "9999992",
            },
            {
                "id": 32149551391255,
                "status": "Updated",
                "email": "python_test_3@kippteamandfamily.org",
                "external_id": "9999993",
            },
            {
                "id": 32149551391127,
                "status": "Updated",
                "email": "python_test_4@apps.teamschools.org",
                "external_id": "9999994",
            },
        ],
    }
}
