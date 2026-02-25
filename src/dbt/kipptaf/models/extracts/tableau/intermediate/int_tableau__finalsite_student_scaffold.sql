/* denominator groupings for inquiries, applications, waitlisted, offers, assigned
   school and accepted */
select
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    status_group_denominator as grouped_status,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,

    'All' as aligned_enrollment_type,

    max(status_start_date) as status_start_date,

from {{ ref("int_students__finalsite_student_roster") }}
where
    status_group_denominator is not null
    and status_start_date is not null
    and not qa_flag
group by
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    status_group_denominator,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status

union all

-- denominator for conversion metrics groupings 
select
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    conversion_metric_denominator as grouped_status,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,

    'All' as aligned_enrollment_type,

    max(status_start_date) as status_start_date,

from {{ ref("int_students__finalsite_student_roster") }}
where
    conversion_metric_denominator is not null
    and status_start_date is not null
    and not qa_flag
group by
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    conversion_metric_denominator,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status

union all

-- currently enrolled numerator
select
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    detailed_status as grouped_status,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,

    'All' as aligned_enrollment_type,

    status_start_date,

from {{ ref("int_students__finalsite_student_roster") }}
where detailed_status = 'Enrolled' and status_start_date is not null and not qa_flag

union all

/* numerator groupings for pending offer and currently accepted */
select
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    status_group_numerator as grouped_status,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,

    'All' as aligned_enrollment_type,

    max(status_start_date) as status_start_date,

from {{ ref("int_students__finalsite_student_roster") }}
where
    status_group_numerator is not null and status_start_date is not null and not qa_flag
group by
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    status_group_numerator,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status

union all

-- numerator for conversion metrics groupings 
select
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    conversion_metric_numerator as grouped_status,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,

    'All' as aligned_enrollment_type,

    max(status_start_date) as status_start_date,

from {{ ref("int_students__finalsite_student_roster") }}
where
    conversion_metric_numerator is not null
    and status_start_date is not null
    and not qa_flag
group by
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    conversion_metric_numerator,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status
