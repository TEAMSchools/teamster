with
    current_assignments as (
        select mail, survey, survey_round, academic_year, link, completion,
        from {{ ref("rpt_tableau__survey_links") }}
        where
            is_current
            and academic_year = {{ var("current_academic_year") }}
            and survey not in ('TNTP Insight Survey', 'Gallup Q12 Survey')
    ),

    open_window as (
        -- grain projection, not dup-masking: one row per academic_year
        select distinct academic_year,
        from current_assignments
        where survey_round != 'INFO'
    )

select ca.mail as email, ca.survey, ca.survey_round, ca.link,
from current_assignments as ca
inner join open_window as ow on ca.academic_year = ow.academic_year
where ca.completion = 0 and ca.mail is not null
