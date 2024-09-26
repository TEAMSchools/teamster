with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    ),

    parse_region as (
        -- trunk-ignore(sqlfluff/AM04)
        select *, regexp_extract(_dbt_source_relation, r'kipp(\w+)_') as region,
        from union_relations
    )

select
    ar.* except (ar.lep_status, ar.region),

    suf.fleid,
    suf.newark_enrollment_number,
    suf.infosnap_id,
    suf.infosnap_opt_in,
    suf.media_release,
    suf.rides_staff,

    nj.districtcoderesident,
    nj.referral_date,
    nj.parental_consent_eval_date,
    nj.eligibility_determ_date,
    nj.initial_iep_meeting_date,
    nj.parent_consent_intial_iep_date,
    nj.annual_iep_review_meeting_date,
    nj.reevaluation_date,
    nj.parent_consent_obtain_code,
    nj.initial_process_delay_reason,
    nj.special_education_placement,
    nj.time_in_regular_program,
    nj.early_intervention_yn,
    nj.determined_ineligible_yn,
    nj.counseling_services_yn,
    nj.occupational_therapy_serv_yn,
    nj.physical_therapy_services_yn,
    nj.speech_lang_theapy_services_yn,
    nj.other_related_services_yn,
    nj.lepbegindate,
    nj.lependdate,
    nj.gifted_and_talented,

    'kipp' || ar.region as code_location,

    initcap(ar.region) as region,

    coalesce(suf.is_504, false) as is_504,

    /* regional differences */
    case
        when ar.region = 'miami'
        then ar.lep_status
        when ar.lepbegindate is null
        then false
        when ar.lependdate < ar.entrydate
        then false
        when ar.lepbegindate <= ar.exitdate
        then true
        else false
    end as lep_status,
from parse_region as ar
left join
    {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
    on seu.students_dcid = suf.studentsdcid
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="suf") }}
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
    on seu.students_dcid = nj.studentsdcid
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="nj") }}
