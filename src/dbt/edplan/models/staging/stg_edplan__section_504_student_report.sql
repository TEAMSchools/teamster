with
    report as (
        select
            internal_student_id,
            school,
            last_name,
            first_name,
            gender,
            grade_abbrev,
            student_status,
            date_snapshot_section_504_eligibility_y_n,
            date_snapshot_historical_section_504_eligibility_y_n,
            section_504_case_manager,
            event_selector,
            event_type,
            document_id,
            primary_disability,
            secondary_disability,
            third_disability,
            _dagster_partition_date as report_date,

            safe_cast(student_id as int) as student_number,
            safe_cast(state_id as int) as state_studentnumber,

            trim(ethnicity) as ethnicity,
            trim(race_abbrev_csv_list) as race_abbrev_csv_list,

            date(parse_datetime('%Y/%m/%d %k:%M:%S', date_of_birth)) as date_of_birth,
            date(parse_datetime('%Y/%m/%d %k:%M:%S', event_date)) as event_date,
            date(parse_datetime('%Y/%m/%d %k:%M:%S', begin_date)) as begin_date,
            date(parse_datetime('%Y/%m/%d %k:%M:%S', end_date)) as end_date,

            max(_dagster_partition_date) over () as latest_report_date,
        from {{ source("edplan", "src_edplan__section_504_student_report") }}
    )

select * except (latest_report_date),
from report
where report_date = latest_report_date
