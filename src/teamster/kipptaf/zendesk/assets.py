from dagster import AssetExecutionContext, ResourceParam, asset
from zenpy import Zenpy


@asset()
def _asset(context: AssetExecutionContext, zendesk: ResourceParam[Zenpy]):
    ...
