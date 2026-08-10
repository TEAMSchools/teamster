with
    -- Focus records enroll_status per stint while the network treats it as the
    -- student's current standing copied onto every row, so the most recent
    -- stint wins. rn_all is computed in int_focus__student_enrollment.
    current_stint as (
        select student_number, enroll_status,
        from {{ ref("int_focus__student_enrollments") }}
        where rn_all = 1
    ),

    -- Miami student identity from Focus, conformed to the PowerSchool column
    -- names and value domains so it merges into the network student spine below
    -- by column name (full union all corresponding). The conform itself lives
    -- in int_focus__students; this model only picks the columns and attaches
    -- the student-level enroll_status.
    focus_conformed as (
        select
            s._dbt_source_relation,
            s._dbt_source_project,
            s.student_number,
            s.first_name,
            s.middle_name,
            s.last_name,
            s.powerschool_id,
            s.florida_student_number,
            s.florida_education_identifier,
            s.dob,
            s.gender,
            s.ethnicity,
            s.state_studentnumber,

            e.enroll_status,

            -- Focus's free_reduced_meals_program is a CEP direct-certification
            -- flag, not an eligibility status -- every Miami student carries
            -- the same value, and Focus stores nothing resembling the
            -- archive's F/R/P domain. Null until Ops surfaces a real
            -- per-student eligibility field; a school-wide constant would feed
            -- an economic-disadvantage proxy with no signal in it.
            cast(null as string) as lunchstatus,
        from {{ ref("int_focus__students") }} as s
        -- Joined on Focus's own prefixed id. Both sides are Focus-native, so
        -- stripping the 8400 prefix on each just to match them back up is a
        -- round trip -- and it made the join depend on the unprefix rule
        -- holding, which is not a property this join needs.
        left join current_stint as e on s.student_id = e.student_number
    ),

    -- Focus is Miami's system of record for student identity, so the frozen
    -- archive contributes no rows. The 493 departed students the Focus seed
    -- never received are dropped with it.
    powerschool_filtered as (
        select p.*,
        from {{ ref("stg_powerschool__students") }} as p
        where p._dbt_source_project != 'kippmiami'
    )

select *,
from powerschool_filtered

full union all corresponding

select *,
from focus_conformed
