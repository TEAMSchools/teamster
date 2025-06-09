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
    from teamster.core.utils.functions import chunk

    user_payloads = [
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

    chunked_payloads = chunk(obj=user_payloads, size=100)

    running_jobs = []
    failures = []
    jobs_queue = {}

    zendesk = build_zendesk_resource()

    while True:
        try:
            payload = next(chunked_payloads)
        except StopIteration:
            payload = None

        # add job to queue
        print(f"{len(running_jobs)} jobs running...")
        if len(running_jobs) == 30:
            print("Jobs queue full...")
            pass
        elif payload is not None:
            post_response = zendesk.post(
                resource="users/create_or_update_many", json={"users": payload}
            ).json()

            jobs_queue[post_response["job_status"]["id"]] = post_response["job_status"][
                "status"
            ]

        # check status of jobs in queue
        if running_jobs:
            job_statuses = zendesk.get(
                resource="job_statuses/show_many",
                params={"ids": ",".join(running_jobs)},
            ).json()

            for js in job_statuses["job_statuses"]:
                print(js)
                jobs_queue[js["id"]] = js["status"]

                if js["status"] == "completed":
                    failed_results = [
                        r for r in js["results"] if r["status"] == "Failed"
                    ]
                    failures.extend(failed_results)

        running_jobs = [
            id for id, status in jobs_queue.items() if status != "completed"
        ]

        # terminate loop when queue is empty
        if len(running_jobs) == 0:
            break
        else:
            # i += 1
            time.sleep(1)

    print(failures)
