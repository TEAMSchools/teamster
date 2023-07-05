with
    student_enrollments_union as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                ]
            )
        }}
    )

select
    seu.*,

    suf.newark_enrollment_number,
    suf.c_504_status,

    case
        when nj.lepbegindate is null
        then false
        when nj.lependdate < seu.entrydate
        then false
        when nj.lepbegindate <= seu.exitdate
        then true
        else false
    end as lep_status,

    sped.special_education_code,
    ifnull(sped.spedlep, 'No IEP') as spedlep,

    tpd.total_balance as lunch_balance,

    upper(
        case
            when
                seu.academic_year = {{ var("current_academic_year") }}
                and seu.rn_year = 1
            then if(tpd.is_directly_certified, 'F', ifd.eligibility_name)
            when
                seu.academic_year < {{ var("current_academic_year") }}
                and seu.entrydate = seu.current_entrydate
            then if(seu.current_lunchstatus = 'NoD', null, seu.current_lunchstatus)
            else seu.lunch_status
        end
    ) as lunch_status,
    case
        when seu.academic_year = {{ var("current_academic_year") }} and seu.rn_year = 1
        then
            case
                when tpd.is_directly_certified
                then 'Direct Certification'
                when ifd.lunch_application_status is null
                then 'No Application'
                else ifd.lunch_application_status
            end
        when
            seu.academic_year < {{ var("current_academic_year") }}
            and seu.entrydate = seu.current_entrydate
        then seu.current_lunchstatus
        else seu.lunch_status
    end as lunch_application_status,
{# saa.student_web_id,
    saa.student_web_password, #}
from student_enrollments_union seu
left join
    {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
    on seu.students_dcid = suf.studentsdcid
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="suf") }}
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
    on seu.students_dcid = nj.studentsdcid
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="nj") }}
left join
    {{ ref("stg_edplan__njsmart_powerschool") }} as sped
    on seu.student_number = sped.student_number
    and seu.academic_year = sped.academic_year
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="sped") }}
left join
    {{ ref("stg_titan__person_data") }} as tpd
    on seu.student_number = tpd.person_identifier
    and seu.academic_year = tpd.academic_year
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="tpd") }}
left join
    {{ ref("stg_titan__income_form_data") }} as ifd
    on seu.student_number = ifd.student_identifier
    and seu.academic_year = ifd.academic_year
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="ifd") }}
    {# left join
    {{ ref("stg_students__access_accounts") }} as saa
    on seu.student_number = saa.student_number #}
    
