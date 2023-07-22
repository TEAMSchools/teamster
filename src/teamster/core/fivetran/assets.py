import pendulum
from dagster import DataVersion, observable_source_asset


def build_fivetran_asset(
    name, code_location, connector_name, connector_id, group_name, **kwargs
):
    @observable_source_asset(
        name=name,
        key_prefix=[code_location, connector_name],
        metadata={"connector_id": connector_id, "connector_name": connector_name},
        group_name=group_name,
        **kwargs,
    )
    def _asset():
        return DataVersion(str(pendulum.now().timestamp()))

    return _asset
