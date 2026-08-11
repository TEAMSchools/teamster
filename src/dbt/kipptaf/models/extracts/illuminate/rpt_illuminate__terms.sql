-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    schoolid as `01 Site ID`,
    `name` as `02 Term Name`,
    id as `03 Term Num`,
    firstday as `04 Start Date`,
    lastday as `05 End Date`,
    portion as `06 Term Type`,

    if(`name` like '%Summer%', 2, 1) as `07 Session Type ID`,

    concat(academic_year, '-', academic_year + 1) as `08 Academic Year`,

    dcid as `09 Local Term ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_students__terms") }}
where
    -- Miami left Illuminate ahead of AY2026-27
    _dbt_source_project != 'kippmiami'
    -- Excludes the synthetic quarter rows int_students__terms adds for a
    -- handful of historical schoolids whose termbins quarter has no matching
    -- row in the raw terms table (see int_students__terms.sql) -- those carry
    -- no term name or PowerSchool identifiers and are not real
    -- Illuminate-importable terms.
    and `name` is not null
