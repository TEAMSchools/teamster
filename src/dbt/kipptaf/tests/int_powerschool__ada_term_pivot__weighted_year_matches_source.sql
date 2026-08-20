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
/* Exact equality, not a tolerance: int_powerschool__ada_term aggregates in exact
   decimal, so a student-year's rate is identical across its term rows and the pivot's
   coalesce reproduces it bit for bit. An earlier float-sum version of that model
   needed a 0.0015 tolerance here, because a rate on a 3-decimal rounding midpoint
   could round either way between evaluations. Restoring equality is what makes this a
   strict guard -- the wrong-column coalesce it exists to catch produced differences
   up to 0.33, but nothing now excuses a difference of any size. */
where pivot_ada_weighted_year != source_ada_weighted_year
