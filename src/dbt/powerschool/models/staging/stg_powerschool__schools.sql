with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__schools"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    ),

    transformations as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            * except (
                dcid,
                id,
                district_number,
                school_number,
                low_grade,
                high_grade,
                sortorder,
                schoolgroup,
                hist_low_grade,
                hist_high_grade,
                dfltnextschool,
                view_in_portal,
                state_excludefromreporting,
                alternate_school_number,
                fee_exemption_status,
                issummerschool,
                schoolcategorycodesetid,
                whomodifiedid
            ),

            /* column transformations */
            dcid.int_value as dcid,
            id.int_value as id,
            district_number.int_value as district_number,
            school_number.int_value as school_number,
            low_grade.int_value as low_grade,
            high_grade.int_value as high_grade,
            sortorder.int_value as sortorder,
            schoolgroup.int_value as schoolgroup,
            hist_low_grade.int_value as hist_low_grade,
            hist_high_grade.int_value as hist_high_grade,
            dfltnextschool.int_value as dfltnextschool,
            view_in_portal.int_value as view_in_portal,
            state_excludefromreporting.int_value as state_excludefromreporting,
            alternate_school_number.int_value as alternate_school_number,
            fee_exemption_status.int_value as fee_exemption_status,
            issummerschool.int_value as issummerschool,
            schoolcategorycodesetid.int_value as schoolcategorycodesetid,
            whomodifiedid.int_value as whomodifiedid,
        from deduplicate
    )

select
    *,

    case
        high_grade when 12 then 'HS' when 8 then 'MS' when 4 then 'ES'
    end as school_level,
from transformations
