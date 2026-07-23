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
            gpa.schoolid,
            gpa.yearid,
            gpa.gpa_y1,
            gpa.gpa_y1_unweighted,
            gpa.n_failing_y1,

            lb.days_prior,
        from {{ ref("snapshot_powerschool__gpa_term") }} as gpa
        inner join
            lookbacks as lb
            on gpa.dbt_valid_from < lb.as_of_boundary
            and gpa.dbt_valid_to >= lb.as_of_boundary
        where
            gpa.yearid = {{ var("current_academic_year") - 1990 }}
            /* TODO(#4318): drop once dev-relation ghost rows are purged — the prod
               snapshot holds permanently-open zz_cbini_* rows injected 2025-12-03 */
            and regexp_contains(
                gpa._dbt_source_relation, r'\.`kipp[a-z]+_powerschool`\.'
            )
    )

select
    _dbt_source_relation,
    studentid,
    schoolid,
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
group by _dbt_source_relation, studentid, schoolid, yearid
