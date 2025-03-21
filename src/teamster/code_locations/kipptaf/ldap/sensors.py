import json
from datetime import datetime, timezone

from dagster import (
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    define_asset_job,
    sensor,
)

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.ldap.assets import assets
from teamster.libraries.ldap.resources import LdapResource

job = define_asset_job(name=f"{CODE_LOCATION}_ldap_asset_job", selection=assets)


@sensor(name=f"{job.name}_sensor", minimum_interval_seconds=(60 * 10), job=job)
def ldap_asset_sensor(context: SensorEvaluationContext, ldap: LdapResource):
    now_timestamp = datetime.now(timezone.utc).timestamp()

    run_requests = []
    asset_selection = []
    cursor: dict = json.loads(context.cursor or "{}")

    for asset in assets:
        asset_identifier = asset.key.to_python_identifier()
        context.log.info(asset_identifier)

        asset_metadata = asset.metadata_by_key[asset.key]
        search_filter = asset_metadata["search_filter"]

        last_check_timestamp = datetime.fromtimestamp(
            timestamp=cursor.get(asset_identifier, 0), tz=timezone.utc
        ).strftime("%Y%m%d%H%M%S.%f%z")
        context.log.info(last_check_timestamp)

        ldap._connection.search(
            search_base=asset_metadata["search_base"],
            search_filter=(f"(&(whenChanged>={last_check_timestamp}){search_filter})"),
            size_limit=1,
        )

        if len(ldap._connection.entries) > 0:
            asset_selection.append(asset.key)

            cursor[asset_identifier] = now_timestamp

    if asset_selection:
        run_requests.append(
            RunRequest(
                run_key=f"{context.sensor_name}_{now_timestamp}",
                asset_selection=asset_selection,
            )
        )

        return SensorResult(run_requests=run_requests, cursor=json.dumps(cursor))


sensors = [
    ldap_asset_sensor,
]
