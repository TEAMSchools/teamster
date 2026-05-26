with
    union_relations as (
        select
            row_hash,
            student_number,
            state_studentnumber,
            academic_year,
            fiscal_year,
            effective_date,
            effective_end_date,
            spedlep,
            special_education_code,
            special_education,
            nj_se_consenttoimplementdate,
            nj_se_delayreason,
            nj_se_earlyintervention,
            nj_se_eligibilityddate,
            nj_se_initialiepmeetingdate,
            nj_se_lastiepmeetingdate,
            nj_se_parentalconsentdate,
            nj_se_parentalconsentobtained,
            nj_se_placement,
            nj_se_reevaluationdate,
            nj_se_referraldate,
            nj_timeinregularprogram,
            ti_serv_counseling,
            ti_serv_occup,
            ti_serv_other,
            ti_serv_physical,
            ti_serv_speech,
        from {{ ref("stg_edplan__njsmart_powerschool") }}

        union all

        select
            row_hash,
            student_number,
            state_studentnumber,
            academic_year,
            fiscal_year,
            effective_date,
            effective_end_date,
            spedlep,
            special_education_code,
            special_education,
            nj_se_consenttoimplementdate,
            nj_se_delayreason,

            null as nj_se_earlyintervention,

            nj_se_eligibilityddate,
            nj_se_initialiepmeetingdate,
            nj_se_lastiepmeetingdate,
            nj_se_parentalconsentdate,
            nj_se_parentalconsentobtained,
            nj_se_placement,
            nj_se_reevaluationdate,
            nj_se_referraldate,
            nj_timeinregularprogram,
            ti_serv_counseling,
            ti_serv_occup,
            ti_serv_other,
            ti_serv_physical,
            ti_serv_speech,
        from {{ source("edplan", "stg_edplan__njsmart_powerschool_archive") }}
    )

select
    row_hash,
    student_number,
    state_studentnumber,
    academic_year,
    fiscal_year,
    effective_date,
    spedlep,
    special_education_code,
    special_education,
    nj_se_consenttoimplementdate,
    nj_se_delayreason,
    nj_se_earlyintervention,
    nj_se_eligibilityddate,
    nj_se_initialiepmeetingdate,
    nj_se_lastiepmeetingdate,
    nj_se_parentalconsentdate,
    nj_se_parentalconsentobtained,
    nj_se_placement,
    nj_se_reevaluationdate,
    nj_se_referraldate,
    nj_timeinregularprogram,
    ti_serv_counseling,
    ti_serv_occup,
    ti_serv_other,
    ti_serv_physical,
    ti_serv_speech,

    -- Hot staging trims within hot rows only; archive passes effective_end_date
    -- through unchanged. When hot replaces an archived snapshot mid-FY, the
    -- two emit rows for overlapping date ranges. Re-applying lead() across
    -- the unioned set trims each row to day-before-next regardless of source.
    coalesce(
        date_sub(
            lead(effective_date) over (
                partition by student_number, fiscal_year order by effective_date asc
            ),
            interval 1 day
        ),
        date(fiscal_year, 6, 30)
    ) as effective_end_date,

    row_number() over (
        partition by student_number, fiscal_year order by effective_date desc
    ) as rn_student_year_desc,
from union_relations
