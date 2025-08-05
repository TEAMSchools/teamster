select
    _dagster_partition_fiscal_year,
    _dagster_partition_subject,
    actbenchmarkcategory as act_benchmark_category,
    americanindianoralaskanative as american_indian_or_alaska_native,
    asian,
    assessmentid as assessment_id,
    assessmentstatus as assessment_status,
    assessmenttype as assessment_type,
    audio,
    birthdate as birth_date,
    blackorafricanamerican as black_or_african_american,
    classcode as class_code,
    classrenaissanceid as class_renaissance_id,
    classsourcedid as class_sourced_id,
    completeddate as completed_date,
    completeddatelocal as completed_date_local,
    coursecode as course_code,
    coursename as course_name,
    courserenaissanceid as course_renaissance_id,
    coursesourcedid as course_sourced_id,
    currentgrade as current_grade,
    deactivationreason as deactivation_reason,
    districtbenchmarkcategoryname as district_benchmark_category_name,
    districtbenchmarkproficient as district_benchmark_proficient,
    districtidentifier as district_identifier,
    districtname as district_name,
    districtrenaissanceid as district_renaissance_id,
    districtsourcedid as district_sourced_id,
    enrollmentstatus as enrollment_status,
    extratime as extra_time,
    gender,
    grade,
    grade3_passingscore as grade3_passing_score,
    grade3_passingstatus as grade3_passing_status,
    gradeequivalent as grade_equivalent,
    groupid as group_id,
    grouporclassname as group_or_class_name,
    hispanicorlatino as hispanic_or_latino,
    instructionalreadinglevel as instructional_reading_level,
    launchdate as launch_date,
    lexile,
    lexilerange as lexile_range,
    literacyclassification as literacy_classification,
    lowerlexilezoneofproximaldevelopment as lower_lexile_zone_of_proximal_development,
    multirace as multi_race,
    nativehawaiianorotherpacificislander as native_hawaiian_or_other_pacific_islander,
    opengrowthscore as open_growth_score,
    partnershipforassessmentofreadinessforcollegeandcareers
    as partnership_for_assessment_of_readiness_for_college_and_careers,
    quantile,
    renaissancebenchmarkcategoryname as renaissance_benchmark_category_name,
    satbenchmarkcategory as sat_benchmark_category,
    schoolbenchmarkcategoryname as school_benchmark_category_name,
    schoolbenchmarkproficient as school_benchmark_proficient,
    schoolname as school_name,
    schoolrenaissanceid as school_renaissance_id,
    schoolsourcedid as school_sourced_id,
    schoolyear as school_year,
    schoolyearenddate as school_year_end_date,
    schoolyearstartdate as school_year_start_date,
    screeningperiodwindowname as screening_period_window_name,
    screeningwindowenddate as screening_window_end_date,
    screeningwindowstartdate as screening_window_start_date,
    smarterbalancedassessmentconsortium as smarter_balanced_assessment_consortium,
    statebenchmarkassessmentname as state_benchmark_assessment_name,
    statebenchmarkcategoryname as state_benchmark_category_name,
    statebenchmarkproficient as state_benchmark_proficient,
    studentemail as student_email,
    studentfirstname as student_first_name,
    studentlastname as student_last_name,
    studentmiddlename as student_middle_name,
    studentrenaissanceid as student_renaissance_id,
    studentstateid as student_state_id,
    takenat as taken_at,
    takenatbyipaddress as taken_at_by_ip_address,
    teacherdisplayid as teacher_display_id,
    teacheremail as teacher_email,
    teacherfirstname as teacher_first_name,
    teacheridentifier as teacher_identifier,
    teacherlastname as teacher_last_name,
    teachermiddlename as teacher_middle_name,
    teacherrenaissanceid as teacher_renaissance_id,
    teachersourcedid as teacher_sourced_id,
    teacheruserid as teacher_user_id,
    upperlexilezoneofproximaldevelopment as upper_lexile_zone_of_proximal_development,
    white,

    cast(assessmentnumber as int) as assessment_number,
    cast(
        districtbenchmarkmaxpercentilerank as int
    ) as district_benchmark_max_percentile_rank,
    cast(
        districtbenchmarkminpercentilerank as int
    ) as district_benchmark_min_percentile_rank,
    cast(
        districtbenchmarknumberofcategorylevels as int
    ) as district_benchmark_number_of_category_levels,
    cast(districtbenchmarkcategorylevel as int) as district_benchmark_category_level,
    cast(grade3_assessmentattempts as int) as grade3_assessment_attempts,
    cast(percentilerank as int) as percentile_rank,
    cast(renaissanceclientid as int) as renaissance_client_id,
    cast(
        renaissancebenchmarkcategorynumberoflevels as int
    ) as renaissance_benchmark_category_number_of_levels,
    cast(scaledscore as int) as scaled_score,
    cast(schoolbenchmarkcategorylevel as int) as school_benchmark_category_level,
    cast(
        schoolbenchmarkmaxpercentilerank as int
    ) as school_benchmark_max_percentile_rank,
    cast(
        schoolbenchmarkminpercentilerank as int
    ) as school_benchmark_min_percentile_rank,
    cast(
        schoolbenchmarknumberofcategorylevels as int
    ) as school_benchmark_number_of_category_levels,
    cast(schoolidentifier as int) as school_identifier,
    cast(studentdisplayid as int) as student_display_id,
    cast(studentidentifier as int) as student_identifier,
    cast(studentsourcedid as int) as student_sourced_id,
    cast(studentuserid as int) as student_user_id,
    cast(unifiedscore as int) as unified_score,

    cast(estimatedoralreadingfluency as numeric) as estimated_oral_reading_fluency,
    cast(gradeplacement as numeric) as grade_placement,
    cast(normalcurveequivalent as numeric) as normal_curve_equivalent,
    cast(raschscore as numeric) as rasch_score,
    cast(standarderrorofmeasurement as numeric) as standard_error_of_measurement,
    cast(totalcorrect as numeric) as total_correct,
    cast(totalpossible as numeric) as total_possible,
    cast(
        lowerzoneofproximaldevelopment as numeric
    ) as lower_zone_of_proximal_development,
    cast(
        upperzoneofproximaldevelopment as numeric
    ) as upper_zone_of_proximal_development,

    cast(cast(districtstateid as numeric) as int) as district_state_id,
    cast(cast(schoolstateid as numeric) as int) as school_state_id,
    cast(cast(teacherstateid as numeric) as int) as teacher_state_id,
    cast(cast(totaltimeinseconds as numeric) as int) as total_time_in_seconds,
    cast(cast(currentsgp as numeric) as int) as current_sgp,
    cast(
        cast(renaissancebenchmarkcategorylevel as numeric) as int
    ) as renaissance_benchmark_category_level,
    cast(
        cast(renaissancebenchmarkcategorymaxpercentilerank as numeric) as int
    ) as renaissance_benchmark_category_max_percentile_rank,
    cast(
        cast(renaissancebenchmarkcategoryminpercentilerank as numeric) as int
    ) as renaissance_benchmark_category_min_percentile_rank,
    cast(
        cast(studentgrowthpercentilefallfall as numeric) as int
    ) as student_growth_percentile_fall_fall,
    cast(
        cast(studentgrowthpercentilefallspring as numeric) as int
    ) as student_growth_percentile_fall_spring,
    cast(
        cast(studentgrowthpercentilefallwinter as numeric) as int
    ) as student_growth_percentile_fall_winter,
    cast(
        cast(studentgrowthpercentilespringfall as numeric) as int
    ) as student_growth_percentile_spring_fall,
    cast(
        cast(studentgrowthpercentilespringspring as numeric) as int
    ) as student_growth_percentile_spring_spring,
    cast(
        cast(studentgrowthpercentilewinterspring as numeric) as int
    ) as student_growth_percentile_winter_spring,
    cast(
        cast(statebenchmarkcategorylevel as numeric) as int
    ) as state_benchmark_category_level,
    cast(
        cast(statebenchmarkmaxscaledscore as numeric) as int
    ) as state_benchmark_max_scaled_score,
    cast(
        cast(statebenchmarkminscaledscore as numeric) as int
    ) as state_benchmark_min_scaled_score,
    cast(
        cast(statebenchmarknumberofcategorylevels as numeric) as int
    ) as state_benchmark_number_of_category_levels,
from {{ source("renlearn", "src_renlearn__star") }}
