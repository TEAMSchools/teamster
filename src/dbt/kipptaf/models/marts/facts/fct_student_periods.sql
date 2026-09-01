with
    -- Identity only. No fact in this layer publishes a natural student
    -- identifier, so the surrogate keys below are built from the enrollment
    -- spine and fct_student_days is joined on its own primary key instead.
    --
    -- Collapsed to student-day because the spine's grain includes entrydate.
    -- That is a no-op today -- no student has ever held two overlapping
    -- enrollment stints in one source project, 0 pairs across 112,825 -- and the
    -- spine's own error-severity uniqueness test fails the build if that ever
    -- changes, so this group by cannot hide a collision.
    identity as (
        select
            student_number,
            _dbt_source_project,
            calendardate,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "student_number",
                        "_dbt_source_project",
                        "calendardate",
                    ]
                )
            }} as student_day_key,
        from {{ ref("int_students__enrollment_days") }}
        group by student_number, _dbt_source_project, calendardate
    ),

    -- Every value on this fact is read from fct_student_days, never recomputed.
    -- The tier ladder, the eligibility floor and the year-to-date accumulation
    -- are expressed there and only there, so the two facts cannot disagree. All
    -- this model does is decide which day ends each period and pick up that
    -- day's row.
    daily as (
        select
            i.student_number,
            i._dbt_source_project,

            d.date_key,
            d.student_enrollment_key,
            d.term_key,
            d.location_key,
            d.academic_year,
            d.week_start_monday,
            d.membership_value,
            d.n_membership_days_ytd,
            d.n_present_days_ytd,
            d.is_truant,
            d.is_ca_eligible,
            d.ada_tier,
            d.is_chronically_absent,

            date(d.academic_year, 7, 1) as year_start_date,
        from identity as i
        inner join
            {{ ref("fct_student_days") }} as d on i.student_day_key = d.student_day_key
    ),

    -- The period start comes from a rule: July 1 for a year, date_trunc for a
    -- month, and the school week's Monday for a week. Only the week has no
    -- formula, which is why fct_student_days carries week_start_monday.
    spine as (
        select
            d.*,
            period_type,
            case
                period_type
                when 'year'
                then d.year_start_date
                when 'month'
                then date_trunc(d.date_key, month)
                when 'week'
                then d.week_start_monday
            end as period_start_date_key,
        from daily as d
        cross join unnest(['year', 'month', 'week']) as period_type
    ),

    -- A day whose school week is unknown gets no week row. int_students__
    -- calendar_week does not cover every membership day: summer days sit outside
    -- the school year in every region, and Paterson has no coverage at all for
    -- AY2023 or AY2024. Year and month grain are unaffected, because both derive
    -- their bucket from the date itself.
    --
    -- Stated as a filter rather than left implicit. The final join below matches
    -- on period_start_date_key, so a null bucket was already being dropped by
    -- NULL-equality semantics -- correct behaviour arrived at silently, which is
    -- worse than the same behaviour with a reason attached.
    bucketed as (select *, from spine where period_start_date_key is not null),

    -- period_end_date_key is the student's own last membership day inside the
    -- bucket, not the calendar period end. A weekend, a holiday and a mid-period
    -- withdrawal all move it, so two students in the same month can have
    -- different end dates. A bucket with no membership day produces no row,
    -- which is why a withdrawn student stops appearing rather than carrying
    -- forward.
    per_period as (
        select
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,
            period_type,
            period_start_date_key,

            max(if(membership_value = 1, date_key, null)) as period_end_date_key,
        from bucketed
        group by
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,
            period_type,
            period_start_date_key
        having period_end_date_key is not null
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "pp.student_number",
                "pp._dbt_source_project",
                "pp.location_key",
                "pp.academic_year",
                "pp.period_type",
                "pp.period_start_date_key",
            ]
        )
    }} as student_period_key,

    {{ dbt_utils.generate_surrogate_key(["pp.student_number"]) }} as student_key,

    -- Read from the period-end row, so every enrollment attribute reached
    -- through it -- grade level, IEP and ELL status, homeroom teacher -- is the
    -- one that applied as of period end, matching every other value here. The
    -- daily fact already resolved which stint owns each day, so there is no
    -- second choice to make about students with more than one stint at a school.
    b.student_enrollment_key,

    -- Same period-end reading as student_enrollment_key above: the term in
    -- effect on period_end_date_key. A month can span terms, so a period row
    -- has no single term of its own -- this is the term as of period end, which
    -- is the only answer consistent with every other value here.
    b.term_key,

    -- location_key is not projected. It groups per_period above and is a hash
    -- input to student_period_key, but it is derivable from
    -- student_enrollment_key through dim_student_enrollments, and declaring it
    -- here would give the generated marts reference a second edge to
    -- dim_locations alongside that one. The Cube layer reaches location by
    -- traversing the enrollment chain for the same reason.
    pp.academic_year,
    pp.period_type,
    pp.period_start_date_key,
    pp.period_end_date_key,

    -- Read as of period end, not recomputed. n_membership_days_ytd accumulates
    -- by calendar date on fct_student_days, so year, month and week grain all
    -- report the same year-to-date position on the same date.
    b.n_membership_days_ytd,
    b.n_present_days_ytd,
    b.is_truant,
    b.is_ca_eligible,
    b.ada_tier,
    b.is_chronically_absent,
from per_period as pp
inner join
    bucketed as b
    on pp.location_key = b.location_key
    and pp.student_number = b.student_number
    and pp._dbt_source_project = b._dbt_source_project
    and pp.academic_year = b.academic_year
    and pp.period_type = b.period_type
    and pp.period_start_date_key = b.period_start_date_key
    and pp.period_end_date_key = b.date_key
