from datetime import timedelta

from dagster import AssetKey, FreshnessPolicy

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE

adp_wfn_policy = FreshnessPolicy.cron(
    deadline_cron="15 1 * * *",
    lower_bound_delta=timedelta(minutes=45),
    timezone=str(LOCAL_TIMEZONE),
)

# fct_student_attendance_daily materializes on a 0 6,15 * * * cron. As a table,
# is_realized and every is_*_record point-in-time anchor freeze at build time
# instead of self-correcting on read, so a failed build silently serves stale
# anchors for up to ~15 hours. Deadlines sit one hour after each materialization
# tick: a normal build (~2.4 min per #4468) clears it comfortably, while a
# skipped tick trips the policy within the hour instead of going unnoticed.
#
# Trade-off: a materialization landing before the window opens (e.g. 05:58)
# reads FAIL at 07:00 and stays FAIL until the NEXT materialization, not just
# the next tick -- up to ~8 hours if that's the 15:00 run. Low risk here
# because the asset's automation condition triggers on this same
# 0 6,15 * * * tick, so a normal run can't land before 06:00 -- only an
# out-of-band manual/backfill run or instance clock skew would trip this.
attendance_daily_policy = FreshnessPolicy.cron(
    deadline_cron="0 7,16 * * *",
    lower_bound_delta=timedelta(hours=1),
    timezone=str(LOCAL_TIMEZONE),
)

policies: dict[AssetKey, FreshnessPolicy] = {
    AssetKey(["kipptaf", "people", "int_people__staff_roster"]): adp_wfn_policy,
    AssetKey(["kipptaf", "people", "int_people__staff_roster_history"]): adp_wfn_policy,
    AssetKey(["kipptaf", "people", "stg_people__employee_numbers"]): adp_wfn_policy,
    AssetKey(
        ["kipptaf", "adp_workforce_now", "stg_adp_workforce_now__workers"]
    ): adp_wfn_policy,
    AssetKey(
        ["kipptaf", "marts", "fct_student_attendance_daily"]
    ): attendance_daily_policy,
}
