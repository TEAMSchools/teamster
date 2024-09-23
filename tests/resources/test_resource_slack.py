from dagster import EnvVar
from dagster_slack import SlackResource


def test_slack_resource():
    slack = SlackResource(token=EnvVar("SLACK_TOKEN"))

    slack_client = slack.get_client()

    slack_client.chat_postMessage(channel="#dagster-alerts", text="Hello, Slack!")
