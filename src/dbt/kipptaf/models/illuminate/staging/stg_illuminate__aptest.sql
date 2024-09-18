with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("illuminate", "aptest_2024"),
                    source("illuminate", "aptest_2023"),
                    source("illuminate", "aptest_2022"),
                    source("illuminate", "aptest_2021"),
                    source("illuminate", "aptest_2020"),
                    source("illuminate", "aptest_2019"),
                ],
                where="not _fivetran_deleted",
            )
        }}
    ),

    coalesce_years as (
        select
            student_id,
            date_imported,
            last_modified,
            last_modified_by,

            coalesce(
                ap_2023_localstudentid,
                ap_2022_localstudentid,
                ap_2021_localstudentid,
                ap_2020_localstudentid,
                ap_2019_localstudentid
            ) as local_studentid,
            coalesce(ap_2023_id, ap_2022_id, ap_2021_id, ap_2020_id, ap_2019_id) as id,
            coalesce(
                ap_2023_adminyear,
                ap_2022_adminyear,
                ap_2021_adminyear,
                ap_2020_adminyear,
                ap_2019_adminyear
            ) as admin_year,
            coalesce(
                ap_2023_apnumber,
                ap_2022_apnumber,
                ap_2021_apnumber,
                ap_2020_apnumber,
                ap_2019_apnumber
            ) as ap_number,
            coalesce(
                ap_2023_birthdate,
                ap_2022_birthdate,
                ap_2021_birthdate,
                ap_2020_birthdate,
                ap_2019_birthdate
            ) as birth_date,
            coalesce(
                ap_2023_classsectioncode,
                ap_2022_classsectioncode,
                ap_2021_classsectioncode,
                ap_2020_classsectioncode,
                ap_2019_classsectioncode
            ) as class_section_code,
            coalesce(
                ap_2023_examcode,
                ap_2022_examcode,
                ap_2021_examcode,
                ap_2020_examcode,
                ap_2019_examcode
            ) as exam_code,
            coalesce(
                ap_2023_examcodetext,
                ap_2022_examcodetext,
                ap_2021_examcodetext,
                ap_2020_examcodetext,
                ap_2019_examcodetext
            ) as exam_code_text,
            coalesce(
                ap_2023_examgrade,
                ap_2022_examgrade,
                ap_2021_examgrade,
                ap_2020_examgrade,
                ap_2019_examgrade
            ) as exam_grade,
            coalesce(
                ap_2023_irregularitycode1,
                ap_2022_irregularitycode1,
                ap_2021_irregularitycode1,
                ap_2020_irregularitycode1,
                ap_2019_irregularitycode1
            ) as irregularity_code_1,
            coalesce(
                ap_2023_irregularitycode1text,
                ap_2022_irregularitycode1text,
                ap_2021_irregularitycode1text,
                ap_2020_irregularitycode1text,
                ap_2019_irregularitycode1text
            ) as irregularity_code_1_text,
            coalesce(
                ap_2023_irregularitycode2,
                ap_2022_irregularitycode2,
                ap_2021_irregularitycode2,
                ap_2020_irregularitycode2,
                ap_2019_irregularitycode2
            ) as irregularity_code_2,
            coalesce(
                ap_2023_irregularitycode2text,
                ap_2022_irregularitycode2text,
                ap_2021_irregularitycode2text,
                ap_2020_irregularitycode2text,
                ap_2019_irregularitycode2text
            ) as irregularity_code_2_text,
            coalesce(
                ap_2023_studentfirstname,
                ap_2022_studentfirstname,
                ap_2021_studentfirstname,
                ap_2020_studentfirstname,
                ap_2019_studentfirstname
            ) as student_first_name,
            coalesce(
                ap_2023_studentlastname,
                ap_2022_studentlastname,
                ap_2021_studentlastname,
                ap_2020_studentlastname,
                ap_2019_studentlastname
            ) as student_last_name,
            coalesce(
                ap_2023_studentmiddleinitial,
                ap_2022_studentmiddleinitial,
                ap_2021_studentmiddleinitial,
                ap_2020_studentmiddleinitial,
                ap_2019_studentmiddleinitial
            ) as student_middle_initial,
        from union_relations
    )

select
    *,

    cast('20' || admin_year as int) as fiscal_year,
    cast('20' || admin_year as int) - 1 as academic_year,
from coalesce_years
