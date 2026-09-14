with
    checked as (
        select
            student_number,
            discipline,
            final_grad_path_code,
            met_njgpa,
            met_act,
            met_sat,
            met_psat10,
            met_psat_nmsqt,

            case
                final_grad_path_code
                when 'S'
                then not met_njgpa
                when 'E'
                then not met_act or met_njgpa
                when 'D'
                then not met_sat or met_njgpa or met_act
                when 'J'
                then not met_psat10 or met_njgpa or met_act or met_sat
                when 'K'
                then not met_psat_nmsqt or met_njgpa or met_act or met_sat or met_psat10
                else false
            end as contradicts_the_flags,
        from {{ ref("int_students__graduation_path_codes") }}
        where
            grade_level >= 11
            and (
                ps_grad_path_code is null
                or ps_grad_path_code not in ('M', 'N', 'O', 'P')
            )
    )

select
    student_number,
    discipline,
    final_grad_path_code,
    met_njgpa,
    met_act,
    met_sat,
    met_psat10,
    met_psat_nmsqt,
from checked
where contradicts_the_flags
