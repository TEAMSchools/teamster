with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__terms"),
                partition_by="id.int_value, schoolid.int_value",
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
                yearid,
                noofdays,
                schoolid,
                yearlycredithrs,
                termsinyear,
                portion,
                autobuildbin,
                isyearrec,
                periods_per_day,
                days_per_cycle,
                attendance_calculation_code,
                sterms,
                suppresspublicview,
                whomodifiedid
            ),

            /* column transformations */
            dcid.int_value as dcid,
            id.int_value as id,
            yearid.int_value as yearid,
            noofdays.int_value as noofdays,
            schoolid.int_value as schoolid,
            yearlycredithrs.double_value as yearlycredithrs,
            termsinyear.int_value as termsinyear,
            portion.int_value as portion,
            autobuildbin.int_value as autobuildbin,
            isyearrec.int_value as isyearrec,
            periods_per_day.int_value as periods_per_day,
            days_per_cycle.int_value as days_per_cycle,
            attendance_calculation_code.int_value as attendance_calculation_code,
            sterms.int_value as sterms,
            suppresspublicview.int_value as suppresspublicview,
            whomodifiedid.int_value as whomodifiedid,
        from deduplicate
    )

select *, yearid + 1990 as academic_year, yearid + 1991 as fiscal_year,
from transformations
