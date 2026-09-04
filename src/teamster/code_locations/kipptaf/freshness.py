from datetime import timedelta

from dagster import AssetKey, FreshnessPolicy

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE

adp_wfn_policy = FreshnessPolicy.cron(
    deadline_cron="15 1 * * *",
    lower_bound_delta=timedelta(minutes=45),
    timezone=str(LOCAL_TIMEZONE),
)

# Both attendance facts materialize on the same 0 6,15 * * * cron, are both
# tables, and are both the sole published source of what they carry -- so one
# policy, one reason. A failed build silently keeps serving the last-built rows:
# for fct_student_days that is every day-level attendance figure, and for
# fct_student_periods every chronic-absence, ADA-tier and truancy rate, since the
# query-rewrite anchor hook that used to compute those at read time is retired.
#
# Deadlines sit one hour after each materialization tick. A normal build (~2.4
# min per #4468) clears it comfortably, while a skipped tick trips the policy
# within the hour instead of going unnoticed for up to ~15 hours.
#
# Trade-off: a materialization landing before the window opens (e.g. 05:58) reads
# FAIL at 07:00 and stays FAIL until the NEXT materialization, not just the next
# tick -- up to ~8 hours if that is the 15:00 run. Low risk, because both assets'
# automation conditions trigger on this same 0 6,15 * * * tick, so a normal run
# cannot land early; only an out-of-band manual or backfill run, or instance
# clock skew, would trip it.
attendance_facts_policy = FreshnessPolicy.cron(
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
    AssetKey(["kipptaf", "marts", "fct_student_days"]): attendance_facts_policy,
    AssetKey(["kipptaf", "marts", "fct_student_periods"]): attendance_facts_policy,
}
