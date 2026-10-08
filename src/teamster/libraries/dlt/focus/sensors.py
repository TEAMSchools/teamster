import sqlalchemy as sa
from dagster import (
    RunRequest,
    SensorDefinition,
    SensorEvaluationContext,
    SkipReason,
    sensor,
)
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.common.configuration.utils import get_resolved_traces

from teamster.libraries.dlt.focus.assets import (
    FOCUS_SOURCE_NAME,
    _asset_key,
    build_focus_dlt_pipeline,
)
from teamster.libraries.dlt.probe import (
    ProbeTable,
    compute_changed,
    in_flight_run,
    probe_signature,
    stored_signatures,
)


def _build_run_request(
    code_location: str, changed: list[ProbeTable], current: dict[str, dict]
) -> RunRequest:
    """RunRequest for the changed tables, passing their probed signatures.

    The probe payload rides run config (the op's `FocusDltConfig.probe` field):
    the op loads exactly this selection and persists these signatures with the
    load — no re-probe, no gate.
    """
    return RunRequest(
        asset_selection=[_asset_key(code_location, table.name) for table in changed],
        run_config={
            "ops": {
                f"{code_location}__dlt__{FOCUS_SOURCE_NAME}": {
                    "config": {
                        "probe": {table.name: current[table.name] for table in changed}
                    }
                }
            }
        },
        # The in-flight guard skips every tick while this run is non-terminal,
        # so a hung run (e.g. an evicted step pod whose replacement exits on
        # the duplicate-start guard) freezes intraday syncing until this cap.
        # Not tighter: a tick after downtime can select every changed table,
        # and a cap that kills that run keeps the old baselines, so the next
        # tick selects the same tables and is killed again.
        tags={"dagster/max_runtime": "1800"},
    )


def build_focus_dlt_intraday_sensor(
    code_location: str,
    tables: list[ProbeTable],
    sql_database_credentials: ConnectionStringCredentials,
    nightly_schedule_name: str,
    minimum_interval_seconds: int = 900,
) -> SensorDefinition:
    """Build the intraday change-detection sensor for one district's Focus DB.

    Each tick probes every table (COUNT(*) + MAX(cursor); count-only for
    no-cursor tables) over one engine, compares against the baseline stored in
    dlt resource state, and requests a run for only the changed tables —
    unchanged tables are never planned, and an idle tick launches nothing. Skips
    while a run launched by this sensor or by the nightly full-refresh schedule
    is in flight (the baseline advances only on load success, so an in-flight
    table would re-select and double-launch).

    Credentials are closure-captured rather than taken as a Dagster resource,
    matching how the Focus code location already resolves them at import.

    See docs/superpowers/specs/2026-08-10-focus-dlt-probe-gated-sync-design.md.
    """
    sensor_name = f"{code_location}__dlt__{FOCUS_SOURCE_NAME}__intraday_sensor"

    @sensor(
        name=sensor_name,
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=[_asset_key(code_location, table.name) for table in tables],
    )
    def _sensor(context: SensorEvaluationContext) -> RunRequest | SkipReason:
        in_flight = in_flight_run(context.instance, sensor_name, nightly_schedule_name)
        if in_flight is not None:
            return SkipReason(f"run {in_flight.dagster_run.run_id} in flight")

        # dlt logs every config resolution to a per-thread list that it clears
        # only when a traced pipeline step ends, and a tick runs none. Each entry
        # pins that tick's whole pipeline, so without this the long-lived code
        # server grows until OOM-killed. Clearing here, not after the dlt calls,
        # also covers ticks that raised before reaching them.
        get_resolved_traces().clear()

        dlt_pipeline = build_focus_dlt_pipeline(code_location)

        # Restore prior signatures from the destination state table. On a truly
        # first run (no dataset) this raises; treat as no prior state.
        try:
            dlt_pipeline.sync_destination()
        except Exception as e:
            # Expected only on the first tick / a brand-new dataset. A persistent
            # failure here (bad perms, wrong dataset) would full-reload every
            # table every tick, so surface it at warning.
            context.log.warning(
                f"dlt sync_destination failed ({e}); treating all tables as "
                "changed (expected only on first run / new dataset)"
            )

        stored = stored_signatures(dlt_pipeline, FOCUS_SOURCE_NAME)

        # One shared engine for the whole probe, like the op's full-refresh probe.
        engine = sa.create_engine(sql_database_credentials.to_native_representation())
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

        changed = compute_changed(tables, current, stored)

        context.log.info(
            f"focus probe: {len(changed)}/{len(tables)} changed; "
            f"changed={sorted(table.name for table in changed)}"
        )

        if not changed:
            return SkipReason(f"no change across {len(tables)} probed tables")

        return _build_run_request(code_location, changed, current)

    return _sensor
