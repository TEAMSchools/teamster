with
    scores as (
        select
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

            safe_divide(
                if(
                    a.scoretype = 'PERCENT',
                    (a.totalpointvalue * s.scorepoints) / 100,
                    s.scorepoints
                ),
                a.totalpointvalue
            ) as score_percent,
        from {{ ref("int_powerschool__gradebook_assignments") }} as a
        left join
            {{ ref("stg_powerschool__assignmentscore") }} as s
            on a.assignmentsectionid = s.assignmentsectionid
    ),

    school_course_exceptions as (
        select
            cc_yearid,
            cc_schoolid,
            cc_course_number,
            cc_sectionid,
            cc_sections_dcid,

            case  -- noqa: ST02
                when  -- noqa: ST02
                    concat(cc_schoolid, cc_course_number) in (  -- noqa: ST02
                        '73252SEM72250G1',  -- noqa: ST02
                        '73252SEM72250G2',  -- noqa: ST02
                        '73252SEM72250G3',  -- noqa: ST02
                        '73252SEM72250G4',  -- noqa: ST02
                        '133570965SEM72250G1',  -- noqa: ST02
                        '133570965SEM72250G2',  -- noqa: ST02
                        '133570965SEM72250G3',  -- noqa: ST02
                        '133570965SEM72250G4',  -- noqa: ST02
                        '133570965LOG300',  -- noqa: ST02
                        '73252LOG300',  -- noqa: ST02
                        '73258LOG300',  -- noqa: ST02
                        '732514LOG300',  -- noqa: ST02
                        '732513LOG300',  -- noqa: ST02
                        '732514GYM08035G1',  -- noqa: ST02
                        '732514GYM08036G2',  -- noqa: ST02
                        '732514GYM08037G3',  -- noqa: ST02
                        '732514GYM08038G4'  -- noqa: ST02
                    )  -- noqa: ST02
                then true  -- noqa: ST02
                else false  -- noqa: ST02
            end as exclude_from_audit,  -- noqa: ST02
        from {{ ref("base_powerschool__course_enrollments") }}
        where cc_sectionid > 0
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
left join school_course_exceptions as e on s.sections_dcid = e.sectionsdcid
where not e.exclude_from_audit
group by s.assignmentsectionid
