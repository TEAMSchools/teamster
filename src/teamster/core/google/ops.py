from dagster import AssetObservation, Config, OpExecutionContext, op


class ObservationOpConfig(Config):
    asset_keys: list[list[str]]


def build_asset_observation_op(code_location):
    @op(name=f"{code_location}_gsheet_asset_observation_op")
    def _op(context: OpExecutionContext, config: ObservationOpConfig):
        for asset_key in config.asset_keys:
            context.log_event(AssetObservation(asset_key=asset_key))

    return _op
