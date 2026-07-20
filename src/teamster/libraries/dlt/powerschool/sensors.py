import sqlalchemy as sa
from dagster import (
    DagsterRunStatus,
    RunRequest,
    RunsFilter,
    SensorDefinition,
    SensorEvaluationContext,
    SkipReason,
    sensor,
)

from teamster.libraries.dlt.powerschool.assets import (
    _SOURCE_NAME,
    PowerSchoolTable,
    _asset_key,
    _compute_changed,
    _stored_signatures,
    build_powerschool_dlt_pipeline,
    probe_signature,
)
from teamster.libraries.dlt.powerschool.resources import OracleResource
from teamster.libraries.ssh.resources import SSHResource

_IN_FLIGHT_STATUSES = [
    DagsterRunStatus.QUEUED,
    DagsterRunStatus.NOT_STARTED,
    DagsterRunStatus.STARTING,
    DagsterRunStatus.STARTED,
    DagsterRunStatus.CANCELING,
]


def _build_run_request(
    code_location: str,
    changed: list[PowerSchoolTable],
    current: dict[str, dict],
) -> RunRequest:
    """RunRequest for the changed tables, passing their probed signatures.

    The probe payload rides run config (the op's PowerSchoolDltConfig.probe
    field): the op loads exactly this selection and persists these signatures
    with the load — no re-probe, no gate.
    """
    return RunRequest(
        asset_selection=[_asset_key(code_location, table.name) for table in changed],
        run_config={
            "ops": {
                f"{code_location}__powerschool": {
                    "config": {
                        "probe": {table.name: current[table.name] for table in changed}
                    }
                }
            }
        },
        tags={"dagster/max_runtime": "3600"},
    )


def build_powerschool_dlt_intraday_sensor(
    code_location: str,
    tables: list[PowerSchoolTable],
    nightly_schedule_name: str,
    minimum_interval_seconds: int = 900,
) -> SensorDefinition:
    """Build the intraday change-detection sensor for one district.

    Each tick opens the SSH tunnel, probes every intraday table (COUNT(*) +
    MAX(cursor); count-only for no-cursor tables), compares against the
    baseline stored in dlt resource state, and requests a run for only the
    changed tables — unchanged tables are never planned, and an idle tick
    launches nothing. Skips while a run launched by this sensor or by the
    nightly full-refresh schedule is in flight (the baseline advances only on
    load success, so an in-flight table would re-select and double-launch).
    See docs/superpowers/specs/2026-07-20-powerschool-dlt-intraday-sensor-design.md.
    """
    sensor_name = f"{code_location}__powerschool__dlt__intraday_sensor"

    @sensor(
        name=sensor_name,
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=[_asset_key(code_location, table.name) for table in tables],
    )
    def _sensor(
        context: SensorEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ) -> RunRequest | SkipReason:
        for tag, value in (
            ("dagster/sensor_name", sensor_name),
            ("dagster/schedule_name", nightly_schedule_name),
        ):
            records = context.instance.get_run_records(
                filters=RunsFilter(tags={tag: value}, statuses=_IN_FLIGHT_STATUSES),
                limit=1,
            )
            if records:
                return SkipReason(
                    f"run {records[0].dagster_run.run_id} in flight ({value})"
                )

        dlt_pipeline = build_powerschool_dlt_pipeline(code_location)

        with ssh_powerschool.open_ssh_tunnel():
            connection_url = db_powerschool.connection_url()

            # Restore prior signatures from the destination state table. On a
            # truly first run (no dataset) this raises; treat as no prior state.
            try:
                dlt_pipeline.sync_destination()
            except Exception as e:
                context.log.info(
                    f"dlt sync_destination failed ({e}); treating all tables as changed"
                )

            stored = _stored_signatures(dlt_pipeline, _SOURCE_NAME)

            # One shared engine over the single tunnel, like the op's probe.
            engine = sa.create_engine(connection_url)
            try:
                with engine.connect() as connection:
                    current: dict[str, dict] = {
                        table.name: probe_signature(
                            connection, table.name, table.cursor_column
                        )
                        for table in tables
                    }
            finally:
                engine.dispose()

        changed = _compute_changed(tables, current, stored)

        context.log.info(
            f"powerschool probe: {len(changed)}/{len(tables)} changed; "
            f"changed={sorted(table.name for table in changed)}"
        )

        if not changed:
            return SkipReason(f"no change across {len(tables)} probed tables")

        return _build_run_request(code_location, changed, current)

    return _sensor
