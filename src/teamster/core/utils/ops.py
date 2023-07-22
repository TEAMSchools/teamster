from dagster import AssetObservation, Config, OpExecutionContext, op


class ObservationOpConfig(Config):
    asset_keys: list


@op
def asset_observation_op(context: OpExecutionContext, config: ObservationOpConfig):
    for asset_key in config.asset_keys:
        context.log_event(AssetObservation(asset_key=asset_key))
