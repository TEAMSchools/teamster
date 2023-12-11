from dagster import ConfigurableResource
from dagster._core.execution.context.init import InitResourceContext
from zenpy import Zenpy


class ZendeskResource(ConfigurableResource):
    def setup_for_execution(self, context: InitResourceContext) -> None:
        Zenpy(
            domain="zendesk.com",
            subdomain=None,
            email=None,
            token=None,
            oauth_token=None,
            password=None,
            session=None,
            anonymous=False,
            timeout=None,
            ratelimit_budget=None,
            proactive_ratelimit=None,
            proactive_ratelimit_request_interval=10,
            disable_cache=False,
        )
