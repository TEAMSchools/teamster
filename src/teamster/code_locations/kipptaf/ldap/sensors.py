import json

import pendulum
from dagster import RunRequest, SensorEvaluationContext, SensorResult, sensor

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.ldap.assets import assets
from teamster.libraries.ldap.resources import LdapResource


@sensor(
    name=f"{CODE_LOCATION}_ldap_asset_sensor",
    minimum_interval_seconds=(60 * 10),
    asset_selection=assets,
)
def ldap_asset_sensor(context: SensorEvaluationContext, ldap: LdapResource):
    now_timestamp = pendulum.now().timestamp()

    cursor: dict = json.loads(context.cursor or "{}")

    asset_selection = []

    for asset in assets:
        asset_identifier = asset.key.to_python_identifier()
        context.log.info(asset_identifier)

        asset_metadata = asset.metadata_by_key[asset.key]
        search_filter = asset_metadata["search_filter"]

        last_check_timestamp = pendulum.from_timestamp(
            cursor.get(asset_identifier, 0)
        ).format(fmt="YYYYMMDDHHmmss.SSSSSSZZ")
        context.log.info(last_check_timestamp)

        ldap._connection.search(
            search_base=asset_metadata["search_base"],
            search_filter=(f"(&(whenChanged>={last_check_timestamp}){search_filter})"),
            size_limit=1,
        )

        if len(ldap._connection.entries) > 0:
            asset_selection.append(asset.key)

            cursor[asset_identifier] = now_timestamp

    return SensorResult(
        run_requests=[
            RunRequest(
                run_key=f"{CODE_LOCATION}_ldap_sensor_{now_timestamp}",
                asset_selection=asset_selection,
            )
        ],
        cursor=json.dumps(cursor),
    )


sensors = [
    ldap_asset_sensor,
]
