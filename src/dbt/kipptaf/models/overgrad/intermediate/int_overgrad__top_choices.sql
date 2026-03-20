with
    ranked_choices as (
        select
            student__external_student_id,
            top_choice_schools,
            university_name,
            university__ipeds_id,

            row_number() over (
                partition by student__external_student_id, top_choice_schools
                order by university_name asc
            ) as rn_choice_dedup,
        from {{ ref("int_overgrad__admissions") }}
        where top_choice_schools is not null
    ),

select
    rc.student__external_student_id as contact_id,

    max(
        if(rc.top_choice_schools = '#1 Choice', true, false)
    ) as has_overgrad_1st_choice,

    max(
        case
            when rc.top_choice_schools = '#1 Choice' and rc.rn_choice_dedup = 1
            then rc.university_name
        end
    ) as overgrad_1st_choice_school_name,
    max(
        case
            when rc.top_choice_schools = '#2 Choice' and rc.rn_choice_dedup = 1
            then rc.university_name
        end
    ) as overgrad_2nd_choice_school_name,
    max(
        case
            when rc.top_choice_schools = '#3 Choice' and rc.rn_choice_dedup = 1
            then rc.university_name
        end
    ) as overgrad_3rd_choice_school_name,

    max(
        case
            when rc.top_choice_schools = '#1 Choice' and rc.rn_choice_dedup = 1
            then acc.adjusted_6_year_minority_graduation_rate
        end
    ) as overgrad_1st_choice_ecc,

    max(
        case
            when rc.top_choice_schools = '#1 Choice' and rc.rn_choice_dedup = 1
            then app.is_submitted
        end
    ) as overgrad_1st_choice_is_submitted,
    max(
        case
            when rc.top_choice_schools = '#1 Choice' and rc.rn_choice_dedup = 1
            then app.is_accepted
        end
    ) as overgrad_1st_choice_is_accepted,
from ranked_choices as rc
left join
    {{ ref("stg_kippadb__account") }} as acc
    on safe_cast(rc.university__ipeds_id as string) = acc.nces_id
left join
    {{ ref("base_kippadb__application") }} as app
    on rc.student__external_student_id = app.applicant
    and acc.id = app.school
group by rc.student__external_student_id
