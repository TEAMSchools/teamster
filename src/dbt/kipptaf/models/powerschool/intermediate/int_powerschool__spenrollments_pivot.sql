with
    filtered as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            specprog_name,
            enter_date,
            exit_date,
            sp_comment,
        from {{ ref("int_powerschool__spenrollments") }}
        where rn_student_program_year_desc = 1
    )

select
    _dbt_source_relation,
    studentid,
    academic_year,

    enter_date_student_athlete,
    exit_date_student_athlete,
    sp_comment_student_athlete,
    enter_date_counseling_services,
    exit_date_counseling_services,
    sp_comment_counseling_services,
    enter_date_home_instruction,
    exit_date_home_instruction,
    sp_comment_home_instruction,
    enter_date_tutoring,
    exit_date_tutoring,
    sp_comment_tutoring,

    if(
        current_date('{{ var("local_timezone") }}')
        between enter_date_student_athlete and exit_date_student_athlete,
        1,
        null
    ) as is_student_athlete,

    if(
        current_date('{{ var("local_timezone") }}')
        between enter_date_counseling_services and exit_date_counseling_services,
        1,
        null
    ) as is_counseling_services,

    if(
        current_date('{{ var("local_timezone") }}')
        between enter_date_home_instruction and exit_date_home_instruction,
        1,
        null
    ) as is_home_instruction,

    if(
        current_date('{{ var("local_timezone") }}')
        between enter_date_tutoring and exit_date_tutoring,
        true,
        false
    ) as is_tutoring,

    if(
        current_date('{{ var("local_timezone") }}')
        between enter_date_bucket_2_ela and exit_date_bucket_2_ela,
        1,
        null
    ) as bucket_2_ela,

    if(
        current_date('{{ var("local_timezone") }}')
        between enter_date_bucket_2_math and exit_date_bucket_2_math,
        1,
        null
    ) as bucket_2_math,
from
    filtered pivot (
        max(enter_date) as enter_date,
        max(exit_date) as exit_date,
        max(sp_comment) as sp_comment
        for specprog_name in (
            'Student Athlete' as `student_athlete`,
            'Counseling Services' as `counseling_services`,
            'Home Instruction' as `home_instruction`,
            'Tutoring' as `tutoring`,
            'Bucket 2 - ELA' as `bucket_2_ela`,
            'Bucket 2 - Math' as `bucket_2_math`
        )
    )
