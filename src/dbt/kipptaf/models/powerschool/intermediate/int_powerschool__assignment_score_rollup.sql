with
    scores as (
        select
            a._dbt_source_relation,
            a.sectionsdcid,
            a.assignmentsectionid,

            e.students_dcid,

            concat(e.cc_schoolid, e.courses_credittype) as schoolid_credit_type,

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
        select _dbt_source_relation, dcid,
        from {{ ref("stg_powerschool__sections") }}
        where
            concat(schoolid, course_number) not in (
                '133570965LOG300',
                '133570965SEM72250G1',
                '133570965SEM72250G2',
                '133570965SEM72250G3',
                '133570965SEM72250G4',
                '732513LOG300',
                '732514GYM08035G1',
                '732514GYM08036G2',
                '732514GYM08037G3',
                '732514GYM08038G4',
                '732514LOG300',
                '73252LOG300',
                '73252SEM72250G1',
                '73252SEM72250G2',
                '73252SEM72250G3',
                '73252SEM72250G4',
                '73258LOG300'
            )
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
    school_course_exceptions as e
    on s.sectionsdcid = e.dcid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="e") }}
where
    e.dcid is not null
    and s.schoolid_credit_type
    not in ('30200804COCUR', '30200804RHET', '30200804SCI', '30200804SOC')
group by s._dbt_source_relation, s.assignmentsectionid
