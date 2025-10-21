with
    bucket_programs as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            trim(split(specprog_name, '-')[offset(0)]) as bucket,
            trim(split(specprog_name, '-')[offset(1)]) as discipline,
        from {{ ref("int_powerschool__spenrollments") }}
        where specprog_name like 'Bucket%'
    )

/* Gifted & Talented */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    student_number as `01 Import Student ID`,

    null as `02 State Student ID`,

    student_last_name as `03 Student Last Name`,
    student_first_name as `04 Student First Name`,

    null as `05 Student Middle Name`,

    dob as `06 Birth Date`,

    '127' as `07 Program ID`,
    null as `08 Eligibility Start Date`,
    null as `09 Eligibility End Date`,

    entrydate as `10 Program Start Date`,
    exitdate as `11 Program End Date`,

    concat(academic_year, '-', academic_year + 1) as `12 Academic Year`,

    null as `13 Program Eligibility Code`,
    null as `14 Program Exit Code`,
    null as `15 Site ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_extracts__student_enrollments") }}
where
    academic_year = {{ current_school_year(var("local_timezone")) }}
    and rn_year = 1
    and gifted_and_talented = 'Y'

union all

/* ELL */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    student_number as `01 Import Student ID`,

    null as `02 State Student ID`,

    student_last_name as `03 Student Last Name`,
    student_first_name as `04 Student First Name`,

    null as `05 Student Middle Name`,

    dob as `06 Birth Date`,

    '120' as `07 Program ID`,
    null as `08 Eligibility Start Date`,
    null as `09 Eligibility End Date`,

    entrydate as `10 Program Start Date`,
    exitdate as `11 Program End Date`,

    concat(academic_year, '-', academic_year + 1) as `12 Academic Year`,

    null as `13 Program Eligibility Code`,
    null as `14 Program Exit Code`,
    null as `15 Site ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_extracts__student_enrollments") }}
where
    academic_year = {{ current_school_year(var("local_timezone")) }}
    and rn_year = 1
    and lep_status

union all

/* Buckets */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    s.student_number as `01 Import Student ID`,

    null as `02 State Student ID`,

    s.last_name as `03 Student Last Name`,
    s.first_name as `04 Student First Name`,

    null as `05 Student Middle Name`,

    s.dob as `06 Birth Date`,

    case
        when b.discipline = 'ELA' and b.bucket = 'Bucket 1'
        then 'B1E'
        when b.discipline = 'Math' and b.bucket = 'Bucket 1'
        then 'B1M'
        when b.discipline = 'ELA' and b.bucket = 'Bucket 2'
        then 'B2E'
        when b.discipline = 'Math' and b.bucket = 'Bucket 2'
        then 'B2M'
        when b.discipline = 'ELA' and b.bucket = 'Bucket 3'
        then 'B3E'
        when b.discipline = 'Math' and b.bucket = 'Bucket 3'
        then 'B3M'
        when b.discipline = 'ELA' and b.bucket = 'Bucket 4'
        then 'BUE'
        when b.discipline = 'Math' and b.bucket = 'Bucket 4'
        then 'BUM'
    end as `07 Program ID`,

    null as `08 Eligibility Start Date`,
    null as `09 Eligibility End Date`,

    entrydate as `10 Program Start Date`,
    exitdate as `11 Program End Date`,

    concat(academic_year, '-', academic_year + 1) as `12 Academic Year`,

    null as `13 Program Eligibility Code`,
    null as `14 Program Exit Code`,
    null as `15 Site ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from bucket_programs as b
inner join
    {{ ref("stg_powerschool__students") }} as s
    on b.studentid = s.id
    and {{ union_dataset_join_clause(left_alias="b", right_alias="s") }}
    and s.enroll_status = 0
where academic_year = {{ current_school_year(var("local_timezone")) }}
