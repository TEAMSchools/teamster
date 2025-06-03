import random
import time
from datetime import datetime, timedelta

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


def test_loop():
    from faker import Faker

    from teamster.core.utils.functions import chunk

    fake = Faker()
    # zendesk = build_zendesk_resource()

    fake_payloads = [
        {
            "email": fake.unique.email(),
            "external_id": str(fake.unique.random_int(min=100000, max=999999)),
            "name": fake.name(),
            "suspended": fake.boolean(),
            "role": fake.random_element(elements=["admin", "agent", "end-user"]),
            "user_fields": {
                "organization_id": fake.random_int(),
                "secondary_location": fake.random_element(
                    elements=[None, "18th_ave_campus", "bold", "courage"]
                ),
            },
            # "user_identities": [
            #     {"value": fake.unique.email(), "type": "email"},
            #     {"value": fake.unique.email(), "type": "email"},
            #     {"value": fake.unique.email(), "type": "email"},
            # ],
        }
        for _ in range(6000)
    ]

    chunked_payloads = chunk(obj=fake_payloads, size=100)
    jobs_queue = []
    i = 1

    while True:
        try:
            payload = next(chunked_payloads)
        except StopIteration:
            payload = None

        # add job to queue
        if len(jobs_queue) == 30:
            print("Job queue full...")
            pass
        elif payload is not None:
            completed_at = datetime.now() + timedelta(seconds=random.randint(a=1, b=90))

            jobs_queue.append(
                {"id": i, "status": None, "completed_at": completed_at.timestamp()}
            )
            print(f"JOB{i} CREATED")

        # check status of jobs in queue
        for job in jobs_queue:
            if datetime.now().timestamp() > job["completed_at"]:
                print(f"JOB{job['id']} COMPLETED")
                job["status"] = "completed"

        jobs_queue = [j for j in jobs_queue if j["status"] != "completed"]
        print(f"{len(jobs_queue)} jobs running...")

        # job_ids = ",".join([j["id"] for j in jobs_queue])
        # GET /api/v2/job_statuses/show_many?ids={ids}
        # """job_statuses = {
        #     "job_statuses": [
        #         {"id": "8b726e606741012ffc2d782bcb7848fe", "status": "completed"},
        #         {"id": "e7665094164c498781ebe4c8db6d2af5", "status": "completed"},
        #     ]
        # }"""
        # for js in job_statuses["job_statuses"]:
        #     if js["status"] == "completed":
        #         foo = [jq for jq in jobs_queue if jq["id"] == js["id"]][0]
        #         jobs_queue.remove(foo)

        # terminate loop when queue is empty
        if len(jobs_queue) == 0:
            print("BREAK")
            break
        else:
            i += 1
            time.sleep(1)


"""
[
    {"id": 32149551391511, "email": "python_test_1@kippteamandfamily.org"},
    {"id": 32149551391383, "email": "python_test_2@gmail.com"},
    {"id": 32149551391255, "email": "python_test_3@kippteamandfamily.org"},
    {"id": 32149551391127, "email": "python_test_4@apps.teamschools.org"},
]
"""
