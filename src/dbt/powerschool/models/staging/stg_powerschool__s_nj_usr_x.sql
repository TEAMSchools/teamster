with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__s_nj_usr_x"),
                partition_by="usersdcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        usersdcid,
        smart_salary,
        smart_yearsinlea,
        smart_yearsinnj,
        smart_yearsofexp,
        excl_frm_smart_stf_submissn,
        smart_stafcompenanualsup,
        smart_stafcompnsatnbassal
    ),

    /* column transformations */
    usersdcid.int_value as usersdcid,
    smart_salary.int_value as smart_salary,
    smart_yearsinlea.int_value as smart_yearsinlea,
    smart_yearsinnj.int_value as smart_yearsinnj,
    smart_yearsofexp.int_value as smart_yearsofexp,
    excl_frm_smart_stf_submissn.int_value as excl_frm_smart_stf_submissn,
    smart_stafcompenanualsup.int_value as smart_stafcompenanualsup,
    smart_stafcompnsatnbassal.int_value as smart_stafcompnsatnbassal,
from deduplicate
