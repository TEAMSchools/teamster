import json

import pendulum
from dagster import (
    AssetsDefinition,
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)

from teamster.core.ldap.resources import LdapResource


def build_ldap_asset_sensor(
    code_location, asset_defs: list[AssetsDefinition], minimum_interval_seconds=None
):
    @sensor(
        name=f"{code_location}_ldap_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(context: SensorEvaluationContext, ldap: LdapResource):
        now_timestamp = pendulum.now().timestamp()

        cursor: dict = json.loads(context.cursor or "{}")

        run_requests = []

        for asset in asset_defs:
            asset_identifier = asset.key.to_python_identifier()
            asset_metadata = asset.metadata_by_key[asset.key]

            context.log.info(asset_identifier)
            search_filter = asset_metadata["search_filter"]

            last_check_timestamp = pendulum.from_timestamp(
                cursor.get(asset_identifier, 0)
            ).format(fmt="YYYYMMDDHHmmss.SSSSSSZZ")

            ldap._connection.search(
                search_base=asset_metadata["search_base"],
                search_filter=(
                    f"(&(whenChanged>={last_check_timestamp}){search_filter})"
                ),
                attributes=asset_metadata["attributes"],
                size_limit=1,
            )

            if len(ldap._connection.entries) > 0:
                run_requests.append(
                    RunRequest(
                        run_key=f"{asset_identifier}_{now_timestamp}",
                        asset_selection=[asset.key],
                    )
                )

                cursor[asset_identifier] = now_timestamp

        return SensorResult(run_requests=run_requests, cursor=cursor)

    return _sensor
