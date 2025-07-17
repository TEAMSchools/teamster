with
    scores as (
        select
            a._dbt_source_relation,
            a.sectionsdcid,
            a.assignmentsectionid,

            e.students_dcid,

            coalesce(s.islate, 0) as islate,
            coalesce(s.isexempt, 0) as isexempt,
            coalesce(s.ismissing, 0) as ismissing,

            if(coalesce(s.isexempt, 0) = 0, true, false) as is_expected,

            if(s.scorepoints is null, 1, 0) as is_null,

            if(
                s.scorepoints is null and coalesce(s.ismissing, 0) = 1, 1, 0
            ) as is_null_missing,

            if(
                s.scorepoints is null and coalesce(s.ismissing, 0) = 0, 1, 0
            ) as is_null_not_missing,

            case
                when s.isexempt = 1
                then false
                when s.ismissing = 1 and s.scorepoints is not null
                then true
                when s.scorepoints is not null
                then true
                else false
            end as is_expected_scored,

            round(
                safe_divide(s.scorepoints, a.totalpointvalue) * 100, 2
            ) as score_percent,

        from {{ ref("int_powerschool__gradebook_assignments") }} as a
        /* PS automatically assigns ALL assignments to a student when they enroll into
        a section, including those from before their enrollment date. This join ensures
        assignments are only matched to valid student enrollments */
        left join
            {{ ref("base_powerschool__course_enrollments") }} as e
            on a.sectionsdcid = e.sections_dcid
            and a.duedate >= e.cc_dateenrolled
            and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
            and not e.is_dropped_section
        left join
            {{ ref("stg_powerschool__assignmentscore") }} as s
            on a.assignmentsectionid = s.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
            and e.students_dcid = s.studentsdcid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
    ),

    school_course_exceptions as (
        select s._dbt_source_relation, s.sections_dcid, e.`include`,
        from {{ ref("base_powerschool__sections") }} as s
        inner join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on s.terms_academic_year = e.academic_year
            and s.sections_schoolid = e.school_id
            and s.sections_course_number = e.course_number
            and e.view_name = 'int_powerschool__assignment_score_rollup'
            and e.cte = 'school_course_exceptions'
            and e.course_number is not null
            and e.is_quarter_end_date_range is null

        union all

        select s._dbt_source_relation, s.sections_dcid, e.`include`,
        from {{ ref("base_powerschool__sections") }} as s
        inner join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on s.terms_academic_year = e.academic_year
            and s.sections_schoolid = e.school_id
            and s.courses_credittype = e.credit_type
            and e.view_name = 'int_powerschool__assignment_score_rollup'
            and e.cte = 'school_course_exceptions'
            and e.credit_type is not null
            and e.is_quarter_end_date_range is null

        union all

        select s._dbt_source_relation, s.sections_dcid, e.`include`,
        from {{ ref("base_powerschool__sections") }} as s
        inner join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on s.terms_academic_year = e.academic_year
            and s.sections_course_number = e.course_number
            and e.view_name = 'int_powerschool__assignment_score_rollup'
            and e.cte = 'school_course_exceptions'
            and e.course_number is not null
            and e.is_quarter_end_date_range is not null
    )

select
    s._dbt_source_relation,
    s.assignmentsectionid,

    count(s.students_dcid) as n_students,

    sum(s.islate) as n_late,
    sum(s.isexempt) as n_exempt,
    sum(s.ismissing) as n_missing,
    sum(s.is_null) as n_null,
    sum(s.is_null_missing) as n_is_null_missing,
    sum(s.is_null_not_missing) as n_is_null_not_missing,

    countif(s.is_expected) as n_expected,
    countif(s.is_expected_scored) as n_expected_scored,

    avg(if(s.is_expected_scored, s.score_percent, null)) as avg_expected_scored_percent,

from scores as s
left join
    school_course_exceptions as e1
    on s.sectionsdcid = e1.sections_dcid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="e1") }}
where e1.`include` is null
group by s._dbt_source_relation, s.assignmentsectionid
