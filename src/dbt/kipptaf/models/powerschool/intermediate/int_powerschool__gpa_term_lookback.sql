with
    lookbacks as (
        select
            days_prior,

            /* first instant of the day AFTER (today - days_prior), local —
               i.e. the value in effect at the END of that lookback day */
            timestamp(
                date_add(
                    date_sub(
                        current_date('{{ var("local_timezone") }}'),
                        interval days_prior day
                    ),
                    interval 1 day
                ),
                '{{ var("local_timezone") }}'
            ) as as_of_boundary,
        from unnest([7, 14, 28]) as days_prior
    ),

    matched as (
        select
            gpa._dbt_source_relation,
            gpa.studentid,
            gpa.yearid,
            gpa.gpa_y1,
            gpa.gpa_y1_unweighted,

            lb.days_prior,

            /* the snapshot carries n_failing_y1 = 0 on versions with no gpa_y1,
               which reads as "failing nothing" rather than "not yet graded" */
            if(gpa.gpa_y1 is not null, gpa.n_failing_y1, null) as n_failing_y1,

            /* rows from before the snapshot closed stale labels can overlap a
               boundary; the newest version is the one in effect */
            row_number() over (
                partition by
                    gpa._dbt_source_relation, gpa.studentid, gpa.yearid, lb.days_prior
                order by gpa.dbt_valid_from desc
            ) as rn_version,
        from {{ ref("snapshot_powerschool__gpa_term") }} as gpa
        inner join
            lookbacks as lb
            on gpa.dbt_valid_from < lb.as_of_boundary
            and gpa.dbt_valid_to >= lb.as_of_boundary
        where gpa.yearid = {{ var("current_academic_year") - 1990 }}
    )

select
    _dbt_source_relation,
    studentid,
    yearid,

    {{ extract_source_project() }} as _dbt_source_project,

    max(if(days_prior = 7, gpa_y1, null)) as gpa_y1_1_week_prior,
    max(if(days_prior = 14, gpa_y1, null)) as gpa_y1_2_week_prior,
    max(if(days_prior = 28, gpa_y1, null)) as gpa_y1_4_week_prior,

    max(if(days_prior = 7, gpa_y1_unweighted, null)) as gpa_y1_unweighted_1_week_prior,
    max(if(days_prior = 14, gpa_y1_unweighted, null)) as gpa_y1_unweighted_2_week_prior,
    max(if(days_prior = 28, gpa_y1_unweighted, null)) as gpa_y1_unweighted_4_week_prior,

    max(if(days_prior = 7, n_failing_y1, null)) as n_failing_y1_1_week_prior,
    max(if(days_prior = 14, n_failing_y1, null)) as n_failing_y1_2_week_prior,
    max(if(days_prior = 28, n_failing_y1, null)) as n_failing_y1_4_week_prior,
from matched
where rn_version = 1
group by _dbt_source_relation, studentid, yearid
