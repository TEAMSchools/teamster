select
    os.external_student_id as student_id,
    os.graduation_year,

    ou.name as college_name,
    ou.ipeds_id as nces_id,

    oa.award_letter__books_and_supplies,
    oa.award_letter__federal_direct_subsidized_loan,
    oa.award_letter__federal_direct_unsubsidized_loan,
    oa.award_letter__seog,
    oa.award_letter__grants_and_scholarships,
    oa.award_letter__grants_from_state,
    oa.award_letter__housing_and_meals,
    oa.award_letter__net_cost,
    oa.award_letter__other_scholarships,
    oa.award_letter__out_of_pocket as out_of_pocket_total,
    oa.award_letter__parent_plus_loan,
    oa.award_letter__federal_pell_grant,
    oa.award_letter__private_loan,
    oa.award_letter__cost_of_attendance,
    oa.award_letter__loans,
    oa.award_letter__unmet_need,
    oa.award_letter__unmet_need_with_max_family_contribution,
    oa.award_letter__work_study,

    os.last_name || ', ' || os.first_name as student,

from {{ ref("stg_overgrad__students") }} as os
inner join
    {{ ref("stg_overgrad__admissions") }} as oa
    on os.id = oa.student__id
    and oa.status = 'Enrolled'
inner join {{ ref("stg_overgrad__universities") }} as ou on oa.university__id = ou.id
