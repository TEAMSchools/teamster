with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollments_raw as (
        select
            student_number,
            academic_year,
            entrydate,
            exitdate,
            _dbt_source_relation,
            _dbt_source_project,
        from {{ ref("int_students__student_enrollment_union") }}
    ),

    -- TODO(#4835): two kippcamden students carry a short AY2026 stint and a
    -- full-year stint sharing an entrydate, so the half-open date-range join
    -- below matches both and fans the streak out. Both matches hash to the
    -- SAME student_enrollment_key (entrydate is its only enrollment input), so
    -- collapsing them is information-preserving, not duplicate-masking. A
    -- genuine overlap -- two stints with DIFFERENT entrydates covering one
    -- streak -- still fans out and still fails the PK test, which is correct.
    -- Deduped here rather than in the union: the union should faithfully
    -- represent its source rows, which other consumers may legitimately need.
    --
    -- Known current failure: the PK test below currently fails on one Miami
    -- AY2021 enrollment record whose stint fully contains another stint for
    -- the same student and year (nested containment, not a partial overlap).
    -- This is a Focus source-data defect being corrected at source, not
    -- collapsed here -- do not add a dedupe/filter/severity change for it. A
    -- genuine partial overlap would still fail this test today, by design.
    enrollments as (
        {{
            dbt_utils.deduplicate(
                relation="enrollments_raw",
                partition_by="student_number, academic_year, entrydate, _dbt_source_project",
                order_by="exitdate desc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["st.streak_id", "st._dbt_source_project"]) }}
    as student_attendance_streak_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_project",
                "st.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    st.streak_start_date as streak_start_date_key,
    st.streak_end_date as streak_end_date_key,

    st.academic_year,
    st.att_code as attendance_code,
    st.streak_length_membership,
    st.streak_length_calendar,
from {{ ref("int_students__attendance_streak") }} as st
inner join
    enrollments as enr
    on st.student_number = enr.student_number
    and st.academic_year = enr.academic_year
    and st.streak_start_date >= enr.entrydate
    and st.streak_start_date < enr.exitdate
    and st._dbt_source_project = enr._dbt_source_project
