with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("overgrad", "src_overgrad__admissions"),
                partition_by="id",
                order_by="updated_at desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    d.* except (custom_field_values, student, university, due_date, award_letter),

    /* records */
    d.student.id as student__id,
    s.external_student_id as student__external_student_id,

    d.university.id as university__id,
    d.university.ipeds_id as university__ipeds_id,

    d.due_date.date as due_date__date,
    d.due_date.type as due_date__type,

    d.award_letter.status as award_letter__status,
    d.award_letter.tuition_and_fees as award_letter__tuition_and_fees,
    d.award_letter.housing_and_meals as award_letter__housing_and_meals,
    d.award_letter.books_and_supplies as award_letter__books_and_supplies,
    d.award_letter.transportation as award_letter__transportation,
    d.award_letter.other_education_costs as award_letter__other_education_costs,
    d.award_letter.grants_and_scholarships_from_school
    as award_letter__grants_and_scholarships_from_school,
    d.award_letter.federal_pell_grant as award_letter__federal_pell_grant,
    d.award_letter.grants_from_state as award_letter__grants_from_state,
    d.award_letter.other_scholarships as award_letter__other_scholarships,
    d.award_letter.work_study as award_letter__work_study,
    d.award_letter.federal_perkins_loan as award_letter__federal_perkins_loan,
    d.award_letter.federal_direct_subsidized_loan
    as award_letter__federal_direct_subsidized_loan,
    d.award_letter.federal_direct_unsubsidized_loan
    as award_letter__federal_direct_unsubsidized_loan,
    d.award_letter.parent_plus_loan as award_letter__parent_plus_loan,
    d.award_letter.military_benefits as award_letter__military_benefits,
    d.award_letter.private_loan as award_letter__private_loan,
    d.award_letter.cost_of_attendance as award_letter__cost_of_attendance,
    d.award_letter.grants_and_scholarships as award_letter__grants_and_scholarships,
    d.award_letter.net_cost as award_letter__net_cost,
    d.award_letter.loans as award_letter__loans,
    d.award_letter.other_options as award_letter__other_options,
    d.award_letter.out_of_pocket as award_letter__out_of_pocket,
    d.award_letter.unmet_need as award_letter__unmet_need,
    d.award_letter.unmet_need_with_max_family_contribution
    as award_letter__unmet_need_with_max_family_contribution,
    d.award_letter.seog as award_letter__seog,
from deduplicate as d
left join {{ ref("stg_overgrad__students") }} as s on d.student.id = s.id
