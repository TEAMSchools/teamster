with
    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_extracts__student_enrollments"),
                partition_by="student_number",
                order_by="academic_year desc, entrydate desc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    student_number as local_student_identifier,
    state_studentnumber as state_student_identifier,
    student_name,
    dob as birth_date,
    gender,
    lunch_status,

    gifted_and_talented is not null as is_gifted,

    lep_status is not null as is_ell,
    iep_status = 'With IEP' as has_iep,

    case
        when ethnicity = 'B'
        then 'Black/African American'
        when ethnicity = 'H'
        then 'Hispanic or Latino'
        when ethnicity = 'T'
        then 'Two or More Races'
        when ethnicity = 'W'
        then 'White'
        when ethnicity = 'I'
        then 'American Indian or Alaska Native'
        when ethnicity = 'A'
        then 'Asian'
        when ethnicity = 'P'
        then 'Native Hawaiian or Other Pacific Islander'
        when ethnicity = 'N'
        then 'Not Hispanic or Latino'
        else 'Not Listed'
    end as ethnicity,
from deduplicated
