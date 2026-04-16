with
    source as (
        select *,
        from `teamster-332318`.`kippnewark_powerschool`.`stg_powerschool__students`
    ),

    renamed as (
        select
            student_number,
            dob as birth_date,
            lastfirst as student_name,
            case
                when ethnicity = 'H' then 'Hispanic/Latino' else 'Not Hispanic/Latino'
            end as ethnicity_label,
        from source
    )

select *,
from renamed
