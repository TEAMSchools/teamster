from dagster import EnvVar
from dagster_slack import SlackResource


def test_slack_resource():
    # trunk-ignore(pyright/reportArgumentType)
    slack = SlackResource(token=EnvVar("SLACK_TOKEN").get_value())

    slack_client = slack.get_client()

    exceptions = ["*`foo` errors:*", "bar", "baz", "spam", "eggs", "google.com"]

    slack_client.chat_postMessage(channel="#dagster-alerts", text="\n".join(exceptions))
