with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__gradecalcschoolassoc"
                ),
                partition_by="gradecalcschoolassocid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (gradecalcschoolassocid, gradecalculationtypeid, schoolsdcid),

    /* column transformations */
    gradecalcschoolassocid.int_value as gradecalcschoolassocid,
    gradecalculationtypeid.int_value as gradecalculationtypeid,
    schoolsdcid.int_value as schoolsdcid,
from deduplicate
