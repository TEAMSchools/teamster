with
    -- trunk-ignore(sqlfluff/ST03)
    edplan as (
        select
            ep._dbt_source_relation,
            ep.student_number,
            ep.academic_year,
            ep.spedlep,
            ep.special_education_code,
            ep.nj_se_parentalconsentobtained,
        from {{ ref("int_edplan__njsmart_powerschool_union") }} as ep
        where ep.rn_student_year_desc = 1 and ep.student_number is not null
    ),

    edplan_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="edplan",
                partition_by="_dbt_source_relation, student_number",
                order_by="academic_year desc",
            )
        }}
    ),

    audit_union as (
        select
            s.student_number,
            s.enroll_status,
            s.entrydate,

            coalesce(scf.spedlep, '') as spedlep_ps,
            coalesce(ep.spedlep, '') as spedlep_edplan,

            coalesce(nj.specialed_classification, '') as specialed_classification_ps,
            coalesce(ep.special_education_code, '') as specialed_classification_edplan,

            ep.nj_se_parentalconsentobtained,

            {{ extract_code_location(table="s") }} as code_location,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on s.dcid = scf.studentsdcid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="scf") }}
        inner join
            {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
            on s.dcid = nj.studentsdcid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="nj") }}
        left join edplan_deduplicate as ep on s.student_number = ep.student_number

        union all

        select
            ep.student_number,

            s.enroll_status,
            s.entrydate,

            coalesce(scf.spedlep, '') as spedlep_ps,
            coalesce(ep.spedlep, '') as spedlep_edplan,

            coalesce(nj.specialed_classification, '') as specialed_classification_ps,
            coalesce(ep.special_education_code, '') as specialed_classification_edplan,

            ep.nj_se_parentalconsentobtained,

            {{ extract_code_location(table="ep") }} as code_location,
        from edplan_deduplicate as ep
        left join
            {{ ref("stg_powerschool__students") }} as s
            on ep.student_number = s.student_number
        left join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on s.dcid = scf.studentsdcid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="scf") }}
        left join
            {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
            on s.dcid = nj.studentsdcid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="nj") }}
    )

select distinct *,
from audit_union
where
    spedlep_ps != spedlep_edplan
    or specialed_classification_ps != specialed_classification_edplan
