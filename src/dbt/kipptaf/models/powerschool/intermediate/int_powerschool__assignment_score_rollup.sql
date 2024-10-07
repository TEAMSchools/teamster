with
    scores as (
        select
            a._dbt_source_relation,
            a.sectionsdcid,
            a.assignmentsectionid,

            s.studentsdcid,
            s.islate,
            s.isexempt,
            s.ismissing,

            if(s.isexempt = 0, true, false) as is_expected,

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
        left join
            {{ ref("stg_powerschool__assignmentscore") }} as s
            on a.assignmentsectionid = s.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
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
    s.assignmentsectionid,

    count(s.studentsdcid) as n_students,
    sum(s.islate) as n_late,
    sum(s.isexempt) as n_exempt,
    sum(s.ismissing) as n_missing,

    countif(s.is_expected) as n_expected,
    countif(s.is_expected_scored) as n_expected_scored,

    avg(if(s.is_expected_scored, s.score_percent, null)) as avg_expected_scored_percent,
from scores as s
left join
    school_course_exceptions as e
    on s.sectionsdcid = e.dcid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="e") }}
where e.dcid is not null
group by s.assignmentsectionid
