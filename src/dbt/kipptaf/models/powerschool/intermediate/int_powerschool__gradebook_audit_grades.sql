select
    _dbt_source_relation,
    academic_year,
    yearid,
    studentid,
    sectionid,
    storecode,
    term_percent_grade_adjusted,
    term_grade_points,
    citizenship,
    comment_value,

from {{ ref("base_powerschool__final_grades") }}

union all

select
    _dbt_source_relation,
    academic_year,
    yearid,
    studentid,
    sectionid,
    storecode,
    `percent` as term_percent_grade_adjusted,
    gpa_points as term_grade_points,
    behavior as citizenship,
    comment_value,

from {{ ref("stg_powerschool__storedgrades") }}
where
    academic_year = {{ var("current_academic_year") - 1 }}
    and storecode_type = 'Q'
    and not is_transfer_grade
