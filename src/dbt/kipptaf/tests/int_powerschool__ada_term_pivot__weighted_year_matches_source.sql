with
    source_year as (
        select
            _dbt_source_project,
            studentid,
            academic_year,

            max(ada_weighted_year) as ada_weighted_year,

        from {{ ref("int_powerschool__ada_term") }}
        group by _dbt_source_project, studentid, academic_year
    ),

    compared as (
        select
            p._dbt_source_project,
            p.studentid,
            p.academic_year,
            p.ada_weighted_year as pivot_ada_weighted_year,

            s.ada_weighted_year as source_ada_weighted_year,

            abs(p.ada_weighted_year - s.ada_weighted_year) as abs_difference,

        from {{ ref("int_powerschool__ada_term_pivot") }} as p
        inner join
            source_year as s
            on p._dbt_source_project = s._dbt_source_project
            and p.studentid = s.studentid
            and p.academic_year = s.academic_year
    )

select
    _dbt_source_project,
    studentid,
    academic_year,
    pivot_ada_weighted_year,
    source_ada_weighted_year,
    abs_difference,
from compared
/* tolerance, not exact equality: both sides round to 3 decimals, and a
   distributed float sum has no guaranteed association order, so a rate sitting
   on a rounding midpoint can differ by one unit in the 3rd decimal between two
   evaluations. Observed artifact is at most 0.001 across ~74k student-years;
   the wrong-column coalesce this test guards against produced differences up to
   0.33, averaging ~0.05. */
where abs_difference > 0.0015
