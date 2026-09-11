with
    -- Focus's `school_id` is its internal id (14, 15, 58...), not the network
    -- school number, and it differs from the `school_number` the focus package
    -- exposes (a Florida code like 2332A). Resolve through both hops. The inner
    -- join is also the filter that drops Focus's 3 non-instructional schools
    -- (Applicants, Virtual Franchise, ZZ Course History), which have no
    -- locations row.
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    -- yearid comes from the package's int_powerschool__calendar_day, a left
    -- join to the isyearrec = 1 term window. Some real calendar days fall
    -- outside every window (August pre-service dates, a 15-day Paterson gap);
    -- their yearid and academic_year are null, and nothing downstream requires
    -- either to be non-null.
    powerschool_dated as (
        select
            cd._dbt_source_relation,
            cd._dbt_source_project,
            cd.schoolid,
            cd.insession,
            cd.membershipvalue,
            cd.week_start_date,
            cd.week_end_date,
            cd.date_value,
            cd.date_value as school_date,

            cd.yearid,

            cd.insession = 1 as is_in_session,
            cd.membershipvalue > 0 as is_in_membership,
        from {{ ref("int_powerschool__calendar_day") }} as cd
        -- PowerSchool carries a handful of pre-2000 sentinel junk rows. The old
        -- source (kipptaf's stg_powerschool__calendar_day) nulled their
        -- date_value and this model dropped the nulls; the package's
        -- int_powerschool__calendar_day passes them through, so drop them by
        -- date here instead -- they were never real calendar days.
        where cd.date_value >= date '2000-01-01'
    ),

    -- Dual-exposes the neutral names (`school_date`, `academic_year`,
    -- `is_in_session`, `is_in_membership`) alongside the legacy names
    -- (`date_value`, `yearid`, `insession`, `membershipvalue`) that
    -- `dim_school_calendars` and the NJ-parity gate read.
    powerschool_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            schoolid,
            insession,
            membershipvalue,
            week_start_date,
            week_end_date,
            date_value,
            school_date,
            yearid,
            is_in_session,
            is_in_membership,

            yearid + 1990 as academic_year,
        from powerschool_dated
    ),

    -- int_focus__calendar_day is Focus-native: it emits academic_year and
    -- school_date, and no insession or membershipvalue at all. A row existing there
    -- IS an in-session day, so both flags are constants supplied here.
    focus_conformed as (
        select
            cd._dbt_source_relation,
            cd._dbt_source_project,
            cd.week_start_date,
            cd.week_end_date,

            fs.schoolid,

            cd.school_date as date_value,
            cd.school_date,
            cd.academic_year,

            1 as insession,
            cast(1 as float64) as membershipvalue,
            true as is_in_session,
            true as is_in_membership,

            cd.academic_year - 1990 as yearid,
        from {{ ref("int_focus__calendar_day") }} as cd
        inner join focus_schools as fs on cd.schoolid = fs.focus_school_id
        -- One row. See int_students__sis_cutover for why the boundary is a
        -- floor derived from recorded attendance rather than from Focus row
        -- presence. Focus's calendar before the cutover year is a scaffold,
        -- not the network's calendar of record, and the network keeps no
        -- Miami calendar days before AY2026 (#5193).
        cross join {{ ref("int_students__sis_cutover") }} as c
        where cd.academic_year >= c.focus_start_academic_year
    )

-- `union all` matches columns by POSITION, so both branches list the same
-- 13 columns in the same order. Enumerating also fixes the view's column list:
-- BigQuery sets it at create time and Dagster rebuilds a view only when its
-- raw SQL changes, so a `select *` branch never picks up a column added
-- upstream.
select
    _dbt_source_relation,
    _dbt_source_project,
    schoolid,
    insession,
    membershipvalue,
    week_start_date,
    week_end_date,
    date_value,
    school_date,
    yearid,
    is_in_session,
    is_in_membership,
    academic_year,
from powerschool_conformed

union all

select
    _dbt_source_relation,
    _dbt_source_project,
    schoolid,
    insession,
    membershipvalue,
    week_start_date,
    week_end_date,
    date_value,
    school_date,
    yearid,
    is_in_session,
    is_in_membership,
    academic_year,
from focus_conformed
