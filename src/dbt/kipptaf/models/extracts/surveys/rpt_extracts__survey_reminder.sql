with
    pending as (
        select sc.mail, sc.survey, sc.survey_round, sc.academic_year, sl.link,
        from {{ ref("rpt_tableau__survey_completion") }} as sc
        inner join
            {{ ref("rpt_tableau__survey_links") }} as sl
            on sc.employee_number = sl.employee_number
            and sc.survey = sl.survey
            and sc.academic_year = sl.academic_year
            and sc.survey_round = sl.survey_round
        where
            sc.mail is not null
            and sc.is_current
            and sc.completion = 0
            and sc.academic_year = {{ var("current_academic_year") }}
    ),

    open_window as (
        select distinct academic_year,
        from {{ ref("rpt_tableau__survey_completion") }}
        where
            is_current
            and survey_round != 'INFO'
            and academic_year = {{ var("current_academic_year") }}
    )

select p.mail as email, p.survey, p.survey_round, p.link,
from pending as p
inner join open_window as ow on p.academic_year = ow.academic_year
