select
    ar.* except (ar.spedlep, ar.lunch_status),

    sr.mail as advisor_email,
    sr.communication_business_mobile as advisor_phone,

    sl.username as student_web_id,
    sl.default_password as student_web_password,
    sl.google_email as student_email_google,

    tpd.total_balance as lunch_balance,

    /* regional differences */
    if(
        ar.region = 'Miami', ar.spedlep, sped.special_education_code
    ) as special_education_code,

    coalesce(if(ar.region = 'Miami', ar.spedlep, sped.spedlep), 'No IEP') as spedlep,

    case
        when ar.academic_year < {{ var("current_academic_year") }}
        then ar.lunch_status
        when ar.region = 'Miami'
        then ar.lunch_status
        when ar.rn_year = 1
        then coalesce(if(tpd.is_directly_certified, 'F', null), tpd.eligibility_name)
    end as lunch_status,

    case
        when ar.academic_year < {{ var("current_academic_year") }}
        then ar.lunch_status
        when ar.region = 'Miami'
        then ar.lunch_status
        when ar.rn_year = 1
        then
            case
                when tpd.is_directly_certified
                then 'Direct Certification'
                when tpd.eligibility_determination_reason is null
                then 'No Application'
                else tpd.eligibility || ' - ' || tpd.eligibility_determination_reason
            end
    end as lunch_application_status,
from {{ ref("int_powerschool__student_enrollments") }} as ar
left join
    {{ ref("base_people__staff_roster") }} as sr
    on ar.advisor_teachernumber = sr.powerschool_teacher_number
left join
    {{ ref("stg_people__student_logins") }} as sl
    on ar.student_number = sl.student_number
left join
    {{ ref("int_edplan__njsmart_powerschool_union") }} as sped
    on ar.student_number = sped.student_number
    and ar.academic_year = sped.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="sped") }}
    and sped.rn_student_year_desc = 1
left join
    {{ ref("stg_titan__person_data") }} as tpd
    on ar.student_number = tpd.person_identifier
    and ar.academic_year = tpd.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="tpd") }}
