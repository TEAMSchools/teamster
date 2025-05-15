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
