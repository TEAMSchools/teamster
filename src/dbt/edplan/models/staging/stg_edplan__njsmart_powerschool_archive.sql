select
    academic_year,
    effective_date,
    effective_end_date,

    academic_year + 1 as fiscal_year,

    nullif(nj_se_parental_consentobtained, 'NULL') as nj_se_parentalconsentobtained,
    nullif(special_education, 'NULL') as special_education,
    nullif(spedlep, 'NULL') as spedlep,
    nullif(special_education_code, 'NULL') as special_education_code,

    safe_cast(student_number as int) as student_number,
    safe_cast(state_studentnumber as int) as state_studentnumber,
    safe_cast(nj_se_delayreason as int) as nj_se_delayreason,
    safe_cast(nj_se_placement as int) as nj_se_placement,
    safe_cast(nj_timeinregularprogram as numeric) as nj_timeinregularprogram,
    safe_cast(nj_se_eligibilityddate as date) as nj_se_eligibilityddate,
    safe_cast(nj_se_lastiepmeetingdate as date) as nj_se_lastiepmeetingdate,
    safe_cast(nj_se_parentalconsentdate as date) as nj_se_parentalconsentdate,
    safe_cast(nj_se_reevaluationdate as date) as nj_se_reevaluationdate,
    safe_cast(nj_se_referraldate as date) as nj_se_referraldate,
    safe_cast(nj_se_initialiepmeetingdate as date) as nj_se_initialiepmeetingdate,
    safe_cast(nj_se_consenttoimplementdate as date) as nj_se_consenttoimplementdate,
    safe_cast(row_hash as string) as row_hash,

    if(ti_serv_counseling, 'Y', 'N') as ti_serv_counseling,
    if(ti_serv_occup, 'Y', 'N') as ti_serv_occup,
    if(ti_serv_other, 'Y', 'N') as ti_serv_other,
    if(ti_serv_physical, 'Y', 'N') as ti_serv_physical,
    if(ti_serv_speech, 'Y', 'N') as ti_serv_speech,
from {{ source("edplan", "src_edplan__njsmart_powerschool_archive") }}
