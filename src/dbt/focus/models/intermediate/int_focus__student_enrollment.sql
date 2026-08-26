select
    s.*,

    p.prior_district_label,
    p.prior_state_label,
    p.prior_country_label,
    p.educational_choice_label,
    p.student_offender_transfer_label,
from {{ ref("stg_focus__student_enrollment") }} as s
left join {{ ref("int_focus__student_enrollment__pivot") }} as p on s.id = p.id
