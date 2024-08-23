select
    id,
    created_at,
    updated_at,
    applied_on,
    application_source,
    `status`,
    status_updated_at,
    waitlisted,
    deferred,
    academic_fit,
    probability_of_acceptance,

    student.id as student__id,
    student.external_student_id as student__external_student_id,

    university.id as university__id,
    university.ipeds_id as university__ipeds_id,

    due_date.date as due_date__date,
    due_date.type as due_date__type,

    award_letter.status as award_letter__status,
    award_letter.tuition_and_fees as award_letter__tuition_and_fees,
    award_letter.housing_and_meals as award_letter__housing_and_meals,
    award_letter.books_and_supplies as award_letter__books_and_supplies,
    award_letter.transportation as award_letter__transportation,
    award_letter.other_education_costs as award_letter__other_education_costs,
    award_letter.grants_and_scholarships_from_school
    as award_letter__grants_and_scholarships_from_school,
    award_letter.federal_pell_grant as award_letter__federal_pell_grant,
    award_letter.grants_from_state as award_letter__grants_from_state,
    award_letter.other_scholarships as award_letter__other_scholarships,
    award_letter.work_study as award_letter__work_study,
    award_letter.federal_perkins_loan as award_letter__federal_perkins_loan,
    award_letter.federal_direct_subsidized_loan
    as award_letter__federal_direct_subsidized_loan,
    award_letter.federal_direct_unsubsidized_loan
    as award_letter__federal_direct_unsubsidized_loan,
    award_letter.parent_plus_loan as award_letter__parent_plus_loan,
    award_letter.military_benefits as award_letter__military_benefits,
    award_letter.private_loan as award_letter__private_loan,
    award_letter.cost_of_attendance as award_letter__cost_of_attendance,
    award_letter.grants_and_scholarships as award_letter__grants_and_scholarships,
    award_letter.net_cost as award_letter__net_cost,
    award_letter.loans as award_letter__loans,
    award_letter.other_options as award_letter__other_options,
    award_letter.out_of_pocket as award_letter__out_of_pocket,
    award_letter.unmet_need as award_letter__unmet_need,
    award_letter.unmet_need_with_max_family_contribution
    as award_letter__unmet_need_with_max_family_contribution,
    award_letter.seog as award_letter__seog,
from {{ source("overgrad", "src_overgrad__admissions") }}
