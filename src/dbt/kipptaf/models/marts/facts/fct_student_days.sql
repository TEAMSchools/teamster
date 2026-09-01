with
    daily as (
        select
            ed.student_number,
            ed._dbt_source_project,
            ed.academic_year,
            ed.entrydate,
            ed.calendardate,
            ed.week_start_monday,
            ed.is_in_session_day,

            sch.location_key,

            t.term_key,

            ada.att_code,
            ada.attendancevalue,
            ada.is_present_weighted,
            ada.is_truant,
            ada.is_absent,
            ada.is_tardy,
            ada.is_ontime,
            ada.is_oss,
            ada.is_iss,
            ada.is_suspended,

            coalesce(ada.membershipvalue, ed.membershipvalue) as membershipvalue,
        from {{ ref("int_students__enrollment_days") }} as ed
        -- location_key lands here rather than being joined downstream because
        -- every cumulative count below is per school, and a rate reported at any
        -- other grain is a different number.
        inner join
            {{ ref("int_students__schools") }} as sch
            on ed.schoolid = sch.school_number
            and ed._dbt_source_project = sch._dbt_source_project
        -- Keyed on student-day, deliberately without entrydate. The enrollment
        -- spine and the attendance model can date the same stint differently
        -- across the Focus cutover, and int_students__attendance_daily is unique
        -- on student-day, so dropping entrydate from the key costs no fan-out
        -- and loses no rows.
        left join
            {{ ref("int_students__attendance_daily") }} as ada
            on ed.student_number = ada.student_number
            and ed._dbt_source_project = ada._dbt_source_project
            and ed.calendardate = ada.calendardate
        left join
            {{ ref("dim_terms") }} as t
            on ed.schoolid = t.school_id
            and ed.term = t.term_name
            and ed.academic_year = t.academic_year
            and t.`type` = 'RT'
    ),

    -- Cumulative from the start of the academic year, per school. Break days
    -- contribute zero, so the running total is unchanged across a weekend or a
    -- holiday -- that is the carry-forward, and it needs no gap-filling because
    -- adding zero leaves the value alone. Every row therefore carries a
    -- year-to-date position, which is what lets a chronic-absence question
    -- resolve on any calendar date without an anchor flag.
    --
    -- is_truant carries the same way, for the same reason: it is a status, not
    -- an event, so the answer on a Saturday is the answer from the last day that
    -- recorded attendance. Without the carry it would be null on every break
    -- day while ada_tier beside it resolved, which reads as a defect.
    running as (
        select
            *,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    membershipvalue,
                    0
                )
            ) over (
                partition by
                    student_number, _dbt_source_project, location_key, academic_year
                order by calendardate asc
                rows between unbounded preceding and current row
            ) as n_membership_days_ytd,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    attendancevalue,
                    0
                )
            ) over (
                partition by
                    student_number, _dbt_source_project, location_key, academic_year
                order by calendardate asc
                rows between unbounded preceding and current row
            ) as n_present_days_ytd,

            last_value(is_truant ignore nulls) over (
                partition by
                    student_number, _dbt_source_project, location_key, academic_year
                order by calendardate asc
                rows between unbounded preceding and current row
            ) as is_truant_carried,
        from daily
    ),

    -- ada_tier must be a real column of a prior CTE before is_chronically_absent
    -- can be derived from it -- a select cannot reference its own alias. This is
    -- the only place in the project where the tier ladder is expressed;
    -- fct_student_periods reads these columns rather than recomputing them.
    tiered as (
        select
            *,

            n_membership_days_ytd >= 10 as is_ca_eligible,

            -- n_membership_days_ytd = 0 guard is load-bearing: without it,
            -- 0 >= 0 makes a zero-membership enrollment Tier 3.
            case
                when n_membership_days_ytd = 0
                then null
                when n_present_days_ytd * 100 >= n_membership_days_ytd * 95
                then 'Tier 1'
                when n_present_days_ytd * 10 > n_membership_days_ytd * 9
                then 'Tier 2'
                when n_present_days_ytd * 10 >= n_membership_days_ytd * 8
                then 'Tier 3'
                else 'Tier 4'
            end as ada_tier,
        from running
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "_dbt_source_project",
                "calendardate",
            ]
        )
    }} as student_day_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "_dbt_source_project",
                "academic_year",
                "entrydate",
            ]
        )
    }} as student_enrollment_key,

    calendardate as date_key,
    location_key,
    academic_year,
    week_start_monday,
    is_in_session_day,

    term_key,

    att_code as attendance_code,

    attendancevalue as attendance_value,
    is_present_weighted as present_weight,

    is_truant_carried as is_truant,

    n_membership_days_ytd,
    n_present_days_ytd,
    is_ca_eligible,
    ada_tier,

    membershipvalue as membership_value,

    ada_tier in ('Tier 3', 'Tier 4') as is_chronically_absent,

    cast(is_absent as int64) as is_absent,
    cast(is_tardy as int64) as is_tardy,
    cast(is_ontime as int64) as is_ontime,
    cast(is_oss as int64) as is_oss,
    cast(is_iss as int64) as is_iss,
    cast(is_suspended as int64) as is_suspended,

    -- Null, not 'Present', when no attendance row joined. A carried break day
    -- and a session day with an unrecorded register both land here, and both
    -- mean unknown rather than present.
    case
        when is_absent is null
        then null
        when is_oss = 1
        then 'Out-of-School Suspension'
        when is_iss = 1
        then 'In-School Suspension'
        when is_absent = 1
        then 'Absent'
        when is_tardy = 1
        then 'Tardy'
        else 'Present'
    end as attendance_category,
from tiered
