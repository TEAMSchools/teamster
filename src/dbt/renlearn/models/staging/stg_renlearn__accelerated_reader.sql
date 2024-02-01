select
    _dagster_partition_fiscal_year as `_dagster_partition_fiscal_year`,
    _dagster_partition_subject as `_dagster_partition_subject`,
    americanindianoralaskanative as `american_indian_or_alaska_native`,
    asian as `asian`,
    author as `author`,
    birthdate as `birth_date`,
    blackorafricanamerican as `black_or_african_american`,
    booklevel as `book_level`,
    bookrating as `book_rating`,
    classcode as `class_code`,
    classrenaissanceid as `class_renaissance_id`,
    classsourcedid as `class_sourced_id`,
    contentlanguage as `content_language`,
    contenttitle as `content_title`,
    coursecode as `course_code`,
    coursename as `course_name`,
    courserenaissanceid as `course_renaissance_id`,
    coursesourcedid as `course_sourced_id`,
    datequizcompleted as `date_quiz_completed`,
    datequizcompletedlocal as `date_quiz_completed_local`,
    districtidentifier as `district_identifier`,
    districtname as `district_name`,
    districtrenaissanceid as `district_renaissance_id`,
    districtsourcedid as `district_sourced_id`,
    enrollmentstatus as `enrollment_status`,
    fictionnonfiction as `fiction_non_fiction`,
    gender as `gender`,
    groupid as `group_id`,
    grouporclassname as `group_or_class_name`,
    hispanicorlatino as `hispanic_or_latino`,
    interestlevel as `interest_level`,
    lexilelevel as `lexile_level`,
    multirace as `multi_race`,
    nativehawaiianorotherpacificislander as `native_hawaiian_or_other_pacific_islander`,
    passed as `passed`,
    percentcorrect as `percent_correct`,
    pointsearned as `points_earned`,
    pointspossible as `points_possible`,
    questionscorrect as `questions_correct`,
    questionspresented as `questions_presented`,
    quizdeleted as `quiz_deleted`,
    quiznumber as `quiz_number`,
    quiztype as `quiz_type`,
    renaissanceclientid as `renaissance_client_id`,
    schoolidentifier as `school_identifier`,
    schoolname as `school_name`,
    schoolrenaissanceid as `school_renaissance_id`,
    schoolsourcedid as `school_sourced_id`,
    schoolyear as `school_year`,
    schoolyearenddate as `school_year_end_date`,
    schoolyearstartdate as `school_year_start_date`,
    studentemail as `student_email`,
    studentfirstname as `student_first_name`,
    studentlastname as `student_last_name`,
    studentmiddlename as `student_middle_name`,
    studentrenaissanceid as `student_renaissance_id`,
    teacheremail as `teacher_email`,
    teacherfirstname as `teacher_first_name`,
    teacheridentifier as `teacher_identifier`,
    teacherlastname as `teacher_last_name`,
    teachermiddlename as `teacher_middle_name`,
    teacherrenaissanceid as `teacher_renaissance_id`,
    teachersourcedid as `teacher_sourced_id`,
    teacheruserid as `teacher_user_id`,
    twi as `twi`,
    white as `white`,
    wordcount as `word_count`,
    coalesce(
        audioused.string_value, safe_cast(audioused.double_value as string)
    ) as `audio_used`,
    coalesce(
        currentgrade.string_value, safe_cast(currentgrade.long_value as string)
    ) as `current_grade`,
    coalesce(
        lexilemeasure.string_value, safe_cast(lexilemeasure.int_value as string)
    ) as `lexile_measure`,
    coalesce(
        studentstateid.string_value, safe_cast(studentstateid.double_value as string)
    ) as `student_state_id`,
    coalesce(
        districtstateid.long_value, safe_cast(districtstateid.double_value as int)
    ) as `district_state_id`,
    coalesce(
        schoolstateid.long_value, safe_cast(schoolstateid.double_value as int)
    ) as `school_state_id`,
    coalesce(
        studentidentifier.long_value, safe_cast(studentidentifier.double_value as int)
    ) as `student_identifier`,
    coalesce(
        studentsourcedid.long_value, safe_cast(studentsourcedid.double_value as int)
    ) as `student_sourced_id`,
    coalesce(
        studentuserid.long_value, safe_cast(studentuserid.float_value as int)
    ) as `student_user_id`,
    coalesce(
        teacherstateid.long_value, safe_cast(teacherstateid.double_value as int)
    ) as `teacher_state_id`,
from {{ source("renlearn", "src_renlearn__accelerated_reader") }}
