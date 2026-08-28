with
    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            region,
            academic_year,
            exitdate,
            enroll_status,
            entrycode,
            exitcode,
            grade_level,
            rn_year,
            year_in_school,
            year_in_network,
            is_enrolled_oct01,
            is_enrolled_oct15,
            is_enrolled_mar15,
            dob,
            state,

            ps_schoolid as schoolid,
            startdate as entrydate,
            student_first_name as first_name,
            student_last_name as last_name,

            network_student_number as student_number,
        from {{ ref("int_focus__student_enrollment_roster") }}
    ),

    powerschool_conformed as (
        select *,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        where _dbt_source_project != 'kippmiami'
    ),

    unioned as (
        select *,
        from powerschool_conformed

        full union all corresponding

        select *,
        from focus_conformed
    )

-- PowerSchool keeps the current enrollment in `students` and prior stints in
-- `reenrollments`. A re-entry backdated to a still-open stint's entrydate
-- therefore yields two rows on (student_number, _dbt_source_project,
-- academic_year, entrydate) -- the grain `student_enrollment_key` hashes -- and
-- every mart joining that key double-counts the student. Keep the year's
-- primary stint: rn_year is already ranked exitdate desc upstream, so the
-- survivor is the open stint and its year_in_school / year_in_network stay
-- populated. This drops rows, never key values, so no existing hash changes and
-- no downstream foreign key is orphaned. See #5045.
select *,
from unioned
qualify
    row_number() over (
        partition by student_number, _dbt_source_project, academic_year, entrydate
        order by rn_year
    )
    = 1
