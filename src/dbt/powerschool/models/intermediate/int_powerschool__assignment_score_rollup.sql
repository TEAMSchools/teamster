with
    scores as (
        select
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
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
    )

select
    assignmentsectionid,

    count(studentsdcid) as n_students,
    sum(islate) as n_late,
    sum(isexempt) as n_exempt,
    sum(ismissing) as n_missing,

    countif(is_expected) as n_expected,
    countif(is_expected_scored) as n_expected_scored,

    avg(if(is_expected_scored, score_percent, null)) as avg_expected_scored_percent,
from scores
group by assignmentsectionid
