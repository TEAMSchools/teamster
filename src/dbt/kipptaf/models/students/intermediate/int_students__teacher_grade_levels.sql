with
    -- The section's Lead Teacher is already on the schedule row; co-teachers
    -- are a separate assignment keyed by course_period_id + syear. Union both
    -- so every staff member who taught a section is credited with that
    -- section's scheduled students, mirroring the PowerSchool model's Lead
    -- Teacher + Co-teacher roledef union in section_teacher.
    teacher_students as (
        select
            s.teacher_id as staff_id,
            s.student_id,
            s.course_period_id,
            s.academic_year,
            s._dbt_source_project,
        from {{ ref("int_focus__schedule") }} as s
        where s.teacher_id is not null

        union all

        select
            ct.staff_id,

            s.student_id,
            s.course_period_id,
            s.academic_year,
            s._dbt_source_project,
        from {{ ref("stg_focus__co_teachers") }} as ct
        inner join
            {{ ref("int_focus__schedule") }} as s
            on ct.course_period_id = s.course_period_id
            and ct.syear = s.academic_year
    ),

    -- Focus staff ids are not network teacher/employee numbers. Staff Number
    -- Identifier, Local (a populated custom field on the Focus user) carries
    -- the network employee_number as a string -- verified against prod: every
    -- non-null AY2026 lead-teacher id (77 of 77) and co-teacher id (21 of 21)
    -- resolves to a kippmiami roster employee_number through this field. ein
    -- (Focus's own EIN field) resolves fewer of the same ids and never
    -- disagrees where both are populated, so this field is preferred.
    identified as (
        select
            ts.student_id,
            ts.course_period_id,
            ts.academic_year,
            ts._dbt_source_project,

            u.staff_number_identifier_local as teachernumber,
        from teacher_students as ts
        inner join {{ ref("int_focus__users") }} as u on ts.staff_id = u.staff_id
        where u.staff_number_identifier_local is not null
    ),

    -- The schedule's own course_grade_level is the course's intended grade,
    -- not the student's, and is 99.8% null in Focus. Resolve the student's own
    -- grade level from their enrollment stint instead, matching how the
    -- PowerSchool model derives it from base_powerschool__student_enrollments.
    -- Only AY2026-forward stints are admitted, matching the cutover in
    -- int_students__students, int_students__terms, and
    -- int_students__student_enrollment_union -- the PowerSchool archive branch
    -- below covers every closed year, and the inner join to this CTE in
    -- grade_level_counts drops any earlier Focus schedule rows for lack of a
    -- match.
    grade_level_lookup as (
        select student_number, academic_year, grade_level,
        from {{ ref("int_focus__student_enrollments") }}
        where rn_year = 1 and academic_year >= 2026
    ),

    grade_level_counts as (
        select
            i.teachernumber,
            i.academic_year,
            i._dbt_source_project,

            gl.grade_level,

            count(distinct i.course_period_id) as section_count_distinct,
            count(i.student_id) as student_count,
        from identified as i
        inner join
            grade_level_lookup as gl
            on i.student_id = gl.student_number
            and i.academic_year = gl.academic_year
        group by i.teachernumber, i.academic_year, i._dbt_source_project, gl.grade_level
    ),

    grade_level_counts_window as (
        select
            teachernumber,
            academic_year,
            _dbt_source_project,
            grade_level,
            section_count_distinct,
            student_count,

            sum(student_count) over (
                partition by teachernumber, academic_year
            ) as student_total_all_grades,
        from grade_level_counts
    ),

    percentages as (
        select
            teachernumber,
            academic_year,
            _dbt_source_project,
            grade_level,
            section_count_distinct,
            student_count,
            student_total_all_grades,

            student_count / student_total_all_grades as grade_level_ratio,
        from grade_level_counts_window
    ),

    -- Miami teacher grade-level distribution from Focus, conformed to the
    -- PowerSchool teacher_grade_levels vocabulary so it merges into the network
    -- spine below by column name (full union all corresponding). yearid and
    -- _dbt_source_relation have no Focus source and are omitted; the union
    -- null-fills them.
    focus_conformed as (
        select
            teachernumber,
            academic_year,
            _dbt_source_project,
            grade_level,
            section_count_distinct,
            student_count,
            student_total_all_grades,
            grade_level_ratio,

            row_number() over (
                partition by teachernumber, academic_year
                order by grade_level_ratio desc
            ) as grade_level_rank,
        from percentages
    ),

    powerschool_unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                ]
            )
        }}
    ),

    powerschool_with_project as (
        -- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
        select
            *,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
        from powerschool_unioned
    ),

    -- Miami cuts over to Focus at AY2026, matching the enrollment and terms
    -- unions. The frozen archive keeps every closed year.
    powerschool_conformed as (
        select *,
        from powerschool_with_project
        where _dbt_source_project != 'kippmiami' or academic_year <= 2025
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
