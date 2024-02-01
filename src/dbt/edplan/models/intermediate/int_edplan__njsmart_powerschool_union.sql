with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_edplan__njsmart_powerschool"),
                    ref("stg_edplan__njsmart_powerschool_archive"),
                ]
            )
        }}
    )

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
    rn_row_year_asc,
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
    row_number() over (
        partition by student_number, fiscal_year
        order by _dbt_source_relation desc, effective_date desc
    ) as rn_student_year_desc,
from union_relations
