select
    o.observation_id,
    o.rubric_name,
    o.score as observation_score,
    o.score_averaged_by_strand as strand_score,
    o.list_two_column_a_str as glows,
    o.list_two_column_b_str as grows,
    o.locked,
    o.observed_at_date_local as observed_at,
    o.academic_year,
    gt.name as observation_type,
    gt.abbreviation as observation_type_abbreviation,
-- os.value_score as row_score,
-- m.name as measurement_name,
-- mgm.strand_name,
-- mgm.strand_description,
-- b.value_clean as text_box,
-- coalesce(u.internal_id_int, srh.employee_number) as employee_number,
-- srh.report_to_employee_number as observer_employee_number,
from {{ ref("stg_schoolmint_grow__observations") }} as o
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt
    on o.observation_type = gt.tag_id
left join
    {{ ref("stg_reporting__terms") }} as t
    on gt.abbreviation = t.type
    and o.observed_at_date_local between t.start_date and t.end_date
where o.academic_year = {{ var('current_academic_year') }}
