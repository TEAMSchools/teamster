/* This query combines data from mCLASS benchmark data and mCLASS progress monitoring data.  In order to use this code there are a few tables that must be created.
	Benchmark Data (b) mclass.studentsummary_2023: Download the benchmark data from mCLASS, I saved mine as studentsummary_2023 and import it as a flat file in SQL Server
	Progress Monitor Data (pm) mclass.progressmonitor: Download the progress monitoring data from mCLASS, I saved mine as progressmonitor and import is as a flat file in SQL Server
	Goals (g) mclass.goals: Create a goals table, there is a table you can use to import in the Google Sheet provided (this may change over time)*/

with bm_temp as
(
      select School_Year
            ,Primary_School_ID
            ,District_Name
            ,School_Name
            ,Student_Primary_ID
            ,Student_Last_Name
            ,Student_First_Name
            ,Enrollment_Grade
            ,Reporting_Class_Name
            ,Reporting_Class_ID
            ,Official_Teacher_Name
            ,Official_Teacher_Staff_ID
            ,Assessing_Teacher_Name
            ,Assessing_Teacher_Staff_ID
            ,Assessment
            ,Assessment_Edition
            ,Assessment_Grade
            ,Benchmark_Period
            ,Client_Date
            ,Sync_Date
            ,decoding_nwf_wrc_level
            ,decoding_nwf_wrc_national_norm_percentile
            ,decoding_nwf_wrc_score
            ,decoding_nwf_wrc_semester_growth
            ,decoding_nwf_wrc_year_growth
            ,letter_names_lnf_level
            ,letter_names_lnf_national_norm_percentile
            ,letter_names_lnf_score
            ,letter_names_lnf_semester_growth
            ,letter_names_lnf_year_growth
            ,letter_sounds_nwf_cls_level			
            ,letter_sounds_nwf_cls_national_norm_percentile			
            ,letter_sounds_nwf_cls_score
            ,letter_sounds_nwf_cls_semester_growth				
            ,letter_sounds_nwf_cls_year_growth
            ,phonemic_awareness_psf_level
            ,phonemic_awareness_psf_national_norm_percentile
            ,phonemic_awareness_psf_score
            ,phonemic_awareness_psf_semester_growth
            ,phonemic_awareness_psf_year_growth
            ,reading_accuracy_orf_accu_level
            ,cast(reading_accuracy_orf_accu_national_norm_percentile as string) as reading_accuracy_orf_accu_national_norm_percentile
            ,reading_accuracy_orf_accu_score
            ,reading_accuracy_orf_accu_semester_growth
            ,reading_accuracy_orf_accu_year_growth
            ,reading_comprehension_maze_level
            ,cast(reading_comprehension_maze_national_norm_percentile as string) as reading_comprehension_maze_national_norm_percentile
            ,reading_comprehension_maze_score
            ,reading_comprehension_maze_semester_growth
            ,reading_comprehension_maze_year_growth
            ,reading_fluency_orf_level
            ,cast(reading_fluency_orf_national_norm_percentile as string) as reading_fluency_orf_national_norm_percentile
            ,reading_fluency_orf_score
            ,reading_fluency_orf_semester_growth
            ,reading_fluency_orf_year_growth
            ,word_reading_wrf_level
            ,word_reading_wrf_national_norm_percentile
            ,word_reading_wrf_score
            ,word_reading_wrf_semester_growth
            ,word_reading_wrf_year_growth
            ,composite_level			
            ,cast(composite_national_norm_percentile as string) as composite_national_norm_percentile
            ,cast(composite_score as float64) as composite_score		
            ,composite_semester_growth				
            ,composite_year_growth
      from {{ source("amplify", "src_amplify__benchmark_student_summary") }}
),

/*WITH*/ student AS
(
     select _dbt_source_relation
           ,cast(academic_year as string) as Academic_Year
           ,school_level as School_Level
           ,schoolid as School_ID
           ,school_name as School
           ,school_abbreviation as School_Abbreviation
           ,studentid as Student_ID_Enrollment
           ,student_number as Student_Number_Enrollment
           ,lastfirst as Student_Name
           ,first_name as Student_First_Name
           ,last_name as Student_Last_Name
           ,case when cast(grade_level as string) = '0' then 'K'
                 else cast(grade_level as string) end as Grade_Level
           ,case when is_out_of_district = TRUE then 1
                 else 0 end as OOD
           ,gender as Gender
           ,ethnicity as Ethnicity
           ,case when is_homeless = TRUE then 1
                 else 0 end as Homeless
           ,case when is_504 = TRUE then 1
                 else 0 end as Is_504
           ,case when spedlep in ('No IEP',NULL) then 0
                      else 1 end as SPED 
           ,case when lep_status = TRUE then 1
                 else 0 end as LEP
           ,lunch_application_status as Economically_Disadvantaged
     from {{ ref("base_powerschool__student_enrollments") }}
     where academic_year = 2022 and enroll_status = 0 and rn_year = 1 and grade_level in (0,1,2,3,4)
),

schedule as
(
      select c._dbt_source_relation
            ,cast(c.cc_academic_year as string) as Academic_Year
            ,'KIPP NJ/Miami' as District
            ,d.Region
            ,d.Reporting_School_ID
            ,c.cc_schoolid AS School_ID
            ,d.Name as School
            ,c.cc_studentid as Student_ID_Schedule
            ,e.Student_Number_Enrollment as Student_Number_Schedule --Needed to keep track of students who test at a grade level different from the class they are enrolled at
            ,case when c.courses_course_name in ('ELA GrK','ELA K') then 'K'
                  when c.courses_course_name = 'ELA Gr1' then '1'
                  when c.courses_course_name = 'ELA Gr2' then '2'
                  when c.courses_course_name = 'ELA Gr3' then '3'
                  when c.courses_course_name = 'ELA Gr4' then '4'
                  end as Student_Grade_Level_Schedule
            ,c.cc_teacherid as Teacher_ID
            ,c.teacher_lastfirst as Teacher_Number
            ,c.teacher_lastfirst AS Teacher_Name
            ,c.courses_course_name as Course_Name
            ,c.cc_course_number as Course_Number
            ,c.cc_section_number as Section_Number
            ,x.Expected_Test
      from {{ ref("base_powerschool__course_enrollments") }} as c
      left join {{ ref("stg_people__campus_crosswalk") }}  as d --Using the district and region and school name fields to use with window functions to calculate rates at these slices
      on c.cc_schoolid = d.PowerSchool_School_ID
      left join --This join is needed to bring over the Student_Number onto the scheduling table, as MCLASS data contains only the Student Number field
      (
            select _dbt_source_relation
                  ,cast(academic_year as string) as Academic_Year
                  ,schoolid as School_ID
                  ,studentid as Student_ID
                  ,student_number as Student_Number_Enrollment
                  ,enroll_status
            from {{ ref("base_powerschool__student_enrollments") }}  
            where academic_year = 2022 and enroll_status = 0 and rn_year = 1 and grade_level in (0,1,2,3,4)
      ) as e
      on cast(c.cc_academic_year as string) = e.Academic_Year and c.cc_studentid = e.Student_ID and {{ union_dataset_join_clause(left_alias="c", right_alias="e") }}
      left join grangel.amplify_dibels_expected_tests as x --Custom table that forces a row to be created by student with each of the expected tests throughout the year. This is needed to properly count participation rates.
      on 'Link' = x.Link
      where c.cc_academic_year = 2022 and not c.is_dropped_course and not c.is_dropped_section and c.rn_course_number_year = 1 and c.courses_course_name in ('ELA GrK','ELA K','ELA Gr1','ELA Gr2','ELA Gr3','ELA Gr4') and e.enroll_status = 0
),

benchmark as
(
      select left(School_Year,4) as MCLASS_Academic_Year --Needed to extract the academic year format that matches NJ's syntax
            ,Primary_School_ID as MCLASS_Primary_School_ID
            ,District_Name as MCLASS_District_Name
            ,School_Name as MCLASS_School_Name
            ,Student_Primary_ID as MCLASS_Student_Number
            ,Student_Last_Name as MCLASS_Student_Last_Name
            ,Student_First_Name as MCLASS_Student_First_Name
            ,Enrollment_Grade as MCLASS_Enrollment_Grade
            ,Reporting_Class_Name as MCLASS_Reporting_Class_Name
            ,Reporting_Class_ID as MCLASS_Reporting_Class_ID
            ,Official_Teacher_Name as MCLASS_Official_Teacher_Name
            ,Official_Teacher_Staff_ID as MCLASS_Official_Teacher_Staff_ID
            ,Assessing_Teacher_Name as MCLASS_Assessing_Teacher_Name
            ,Assessing_Teacher_Staff_ID as MCLASS_Assessing_Teacher_Staff_ID
            ,Assessment as MCLASS_Assessment
            ,Assessment_Edition as MCLASS_Assessment_Edition
            ,Assessment_Grade as MCLASS_Assessment_Grade
            ,Benchmark_Period as MCLASS_Period
            ,Client_Date as MCLASS_Client_Date
            ,Sync_Date as MCLASS_Sync_Date
            ,null as MCLASS_Probe_Number
            ,null as MCLASS_Total_Number_of_Probes
            ,measure as MCLASS_Measure
            ,score as MCLASS_Measure_Score
            ,'' as MCLASS_Score_Change
            ,level as MCLASS_Measure_Level
            ,percentile as Measure_Percentile
            ,semester_growth as Measure_Semester_Growth
            ,year_growth as Measure_Year_Growth
      from bm_temp
      unpivot 
      (
        (level,percentile,score,semester_growth, year_growth) for measure in --This chunk both unpivots AND groups the measures of each standard assessed by DIBELS's benchmark test
            (
                  (
                        decoding_nwf_wrc_level,
                        decoding_nwf_wrc_national_norm_percentile,
                        decoding_nwf_wrc_score,
                        decoding_nwf_wrc_semester_growth,
                        decoding_nwf_wrc_year_growth
                  ) as 'Decoding (NWF-WRC)',
                  (
                        letter_names_lnf_level,
                        letter_names_lnf_national_norm_percentile,
                        letter_names_lnf_score,
                        letter_names_lnf_semester_growth,
                        letter_names_lnf_year_growth
                  ) as 'Letter Names (LNF)',
                  (
                        letter_sounds_nwf_cls_level,			
                        letter_sounds_nwf_cls_national_norm_percentile,				
                        letter_sounds_nwf_cls_score,	
                        letter_sounds_nwf_cls_semester_growth,				
                        letter_sounds_nwf_cls_year_growth
                  ) as 'Letter Sounds (NWF-CLS)',
                  (
                        phonemic_awareness_psf_level,
                        phonemic_awareness_psf_national_norm_percentile,
                        phonemic_awareness_psf_score,
                        phonemic_awareness_psf_semester_growth,
                        phonemic_awareness_psf_year_growth
                  ) as 'Phonemic Awareness (PSF)',
                  (
                        reading_accuracy_orf_accu_level,
                        reading_accuracy_orf_accu_national_norm_percentile,
                        reading_accuracy_orf_accu_score,
                        reading_accuracy_orf_accu_semester_growth,
                        reading_accuracy_orf_accu_year_growth
                  ) as 'Reading Accuracy (ORF-Accu)',
                  (
                        reading_comprehension_maze_level,
                        reading_comprehension_maze_national_norm_percentile,
                        reading_comprehension_maze_score,
                        reading_comprehension_maze_semester_growth,
                        reading_comprehension_maze_year_growth
                  ) as 'Reading Comprehension (Maze)',
                  (
                        reading_fluency_orf_level,
                        reading_fluency_orf_national_norm_percentile,
                        reading_fluency_orf_score,
                        reading_fluency_orf_semester_growth,
                        reading_fluency_orf_year_growth
                  ) as 'Reading Fluency (ORF)',
                  (
                        word_reading_wrf_level,
                        word_reading_wrf_national_norm_percentile,
                        word_reading_wrf_score,
                        word_reading_wrf_semester_growth,
                        word_reading_wrf_year_growth
                  ) as 'Word Reading (WRF)',
                  (
                        composite_level,				
                        composite_national_norm_percentile,	
                        composite_score,		
                        composite_semester_growth,				
                        composite_year_growth
                  ) as 'Composite'
            )  
      )
 ),

progress_monitoring as
(
      select left(School_Year,4) as MCLASS_Academic_Year --Needed to extract the academic year format that matches NJ's syntax
            ,Primary_School_ID as MCLASS_Primary_School_ID
            ,District_Name as MCLASS_District_Name
            ,School_Name as MCLASS_School_Name
            ,Student_Primary_ID as MCLASS_Student_Number
            ,Student_Last_Name as MCLASS_Student_Last_Name
            ,Student_First_Name as MCLASS_Student_First_Name
            ,cast(Enrollment_Grade as string) as MCLASS_Enrollment_Grade
            ,Reporting_Class_Name as MCLASS_Reporting_Class_Name
            ,Reporting_Class_ID as MCLASS_Reporting_Class_ID
            ,Official_Teacher_Name as MCLASS_Official_Teacher_Name
            ,Official_Teacher_Staff_ID as MCLASS_Official_Teacher_Staff_ID
            ,Assessing_Teacher_Name as MCLASS_Assessing_Teacher_Name
            ,cast(Assessing_Teacher_Staff_ID as string) as MCLASS_Assessing_Teacher_Staff_ID
            ,Assessment as MCLASS_Assessment
            ,Assessment_Edition as MCLASS_Assessment_Edition
            ,cast(Assessment_Grade as string) as MCLASS_Assessment_Grade
            ,PM_Period as MCLASS_Period
            ,Client_Date as MCLASS_Client_Date
            ,Sync_Date as MCLASS_Sync_Date
            ,Probe_Number as MCLASS_Probe_Number
            ,Total_Number_of_Probes as MCLASS_Total_Number_of_Probes
            ,Measure as MCLASS_Measure
            ,Score as MCLASS_Measure_Score
            ,Score_Change as MCLASS_Score_Change
            ,'' as MCLASS_Measure_Level
            ,'' as Measure_Percentile
            ,'' as Measure_Semester_Growth
            ,'' as Measure_Year_Growth
      from {{ source("amplify", "src_amplify__pm_student_summary") }}
)

select b.Academic_Year
      ,b.District
      ,b.Region
      ,b.School_Level
      ,b.School_ID
      ,b.Reporting_School_ID
      ,b.School
      ,b.School_Abbreviation
      ,b.Student_Number_Enrollment
      ,b.Student_Number_Schedule
      ,b.Student_Name
      ,b.Student_Last_Name
      ,b.Student_First_Name
      ,b.Grade_Level
      ,b.Student_Grade_Level_Schedule
      ,b.OOD
      ,b.Gender
      ,b.Ethnicity
      ,b.Homeless
      ,b.Is_504
      ,b.SPED
      ,b.LEP
      ,b.Economically_Disadvantaged
      ,b.Enrolled_but_not_Scheduled
      ,b.Student_has_Assessment_Data
      ,b.Teacher_ID
      ,b.Teacher_Name
      ,b.Course_Name
      ,b.Course_Number
      ,b.Section_Number
      ,b.Expected_Test
      ,b.MCLASS_District_Name
      ,b.MCLASS_School_Name
      ,b.MCLASS_Student_Number
      ,b.MCLASS_Student_Number_BM
      ,b.MCLASS_Student_Number_PM
      ,b.MCLASS_Student_Last_Name
      ,b.MCLASS_Student_First_Name
      ,b.MCLASS_Enrollment_Grade
      ,b.MCLASS_Reporting_Class_Name
      ,b.MCLASS_Reporting_Class_ID
      ,b.MCLASS_Official_Teacher_Name
      ,b.MCLASS_Official_Teacher_Staff_ID
      ,b.MCLASS_Assessing_Teacher_Name
      ,b.MCLASS_Assessing_Teacher_Staff_ID
      ,b.MCLASS_Assessment
      ,b.MCLASS_Assessment_Edition
      ,b.MCLASS_Assessment_Grade
      ,b.MCLASS_Period
      ,b.MCLASS_Client_Date
      ,b.MCLASS_Sync_Date
      ,b.MCLASS_Probe_Number
      ,b.MCLASS_Total_Number_of_Probes
      ,b.MCLASS_Measure
      ,b.MCLASS_Measure_Score
      ,b.MCLASS_Score_Change
      ,b.MCLASS_Measure_Level
      ,b.Measure_Percentile
      ,b.Measure_Semester_Growth
      ,b.Measure_Year_Growth

      --Participation rates by School_Course_Section
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test) as Participation_School_Course_Section_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test) as Participation_School_Course_Section_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test) end),4) as Participation_School_Course_Section_BM_PM_Period_Percent

      --Participation rates by School_Course
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test) as Participation_School_Course_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test) as Participation_School_Course_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test) end),4) as Participation_School_Course_BM_PM_Period_Percent

      --Participation rates by School_Grade
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test) as Participation_School_Grade_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test) as Participation_School_Grade_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test) end),4) as Participation_School_Grade_BM_PM_Period_Percent
      --Participation rates by School
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test) as Participation_School_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test) as Participation_School_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test) end),4) as Participation_School_BM_PM_Period_Percent

      --Participation rates by Region_Grade
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test) as Participation_Region_Grade_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test) as Participation_Region_Grade_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test) end),4) as Participation_Region_Grade_BM_PM_Period_Percent

      --Participation rates by Region
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Expected_Test) as Participation_Region_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Expected_Test) as Participation_Region_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Expected_Test) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Expected_Test) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Expected_Test) end),4) as Participation_Region_BM_PM_Period_Percent

      --Participation rates by District_Grade
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test) as Participation_District_Grade_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test) as Participation_District_Grade_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test) end),4) as Participation_District_Grade_BM_PM_Period_Percent

      --Participation rates by District
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test) as Participation_District_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test) as Participation_District_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test) end),4) as Participation_District_BM_PM_Period_Percent

      --Measure score met rates by School_Course_Section
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) as Measure_Score_Met_School_Course_Section_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test,b.MCLASS_Measure) as Measure_Score_Met_School_Course_Section_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,
            b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Score_Met_School_Course_Section_BM_PM_Period_Percent

      --Measure score met rates by School_Course
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) as Measure_Score_Met_School_Course_Course_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure) as Measure_Score_Met_School_Course_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Score_Met_School_Course_BM_PM_Period_Percent

      --Measure score met rates by School_Grade
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) as Measure_Score_Met_School_Grade_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) as Measure_Score_Met_School_Grade_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Score_Met_School_Grade_BM_PM_Period_Percent

      --Measure score met rates by School
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) as Measure_Score_Met_School_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure) as Measure_Score_Met_School_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Score_Met_School_BM_PM_Period_Percent

      --Measure score met rates by Region_Grade
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) as Measure_Score_Met_Region_Grade_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) as Measure_Score_Met_Region_Grade_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Score_Met_Region_Grade_BM_PM_Period_Percent

      --Measure score met rates by Region
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) as Measure_Score_Met_Region_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure) as Measure_Score_Met_Region_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Score_Met_Region_BM_PM_Period_Percent

      --Measure score met rates by District_Grade
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) as Measure_Score_Met_District_Grade_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) as Measure_Score_Met_District_Grade_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Score_Met_District_Grade_BM_PM_Period_Percent_Met

      --Measure score met rates by District
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) as Measure_Score_Met_District_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) as Measure_Score_Met_District_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Score) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Score_Met_District_BM_PM_Period_Percent

      --Measure level met rates by School_Course_Section
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) as Measure_Level_Met_School_Course_Section_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test,b.MCLASS_Measure) as Measure_Level_Met_School_Course_Section_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,
            b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Section_Number,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Level_Met_School_Course_Section_BM_PM_Period_Percent

      --Measure level met rates by School_Course
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) as Measure_Level_Met_School_Course_Course_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure) as Measure_Level_Met_School_Course_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Course_Name,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Level_Met_School_Course_BM_PM_Period_Percent

      --Measure level met rates by School_Grade
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) as Measure_Level_Met_School_Grade_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) as Measure_Level_Met_School_Grade_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Level_Met_School_Grade_BM_PM_Period_Percent

      --Measure level met rates by School
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) as Measure_Level_Met_School_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure) as Measure_Level_Met_School_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.School_ID,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Level_Met_School_BM_PM_Period_Percent

      --Measure level met rates by Region_Grade
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) as Measure_Level_Met_Region_Grade_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) as Measure_Level_Met_Region_Grade_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Grade_Level,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Level_Met_Region_Grade_BM_PM_Period_Percent

      --Measure level met rates by Region
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) as Measure_Level_Met_Region_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure) as Measure_Level_Met_Region_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.Region,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Level_Met_Region_BM_PM_Period_Percent

      --Measure level met rates by District_Grade
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) as Measure_Level_Met_District_Grade_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) as Measure_Level_Met_District_Grade_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Level_Met_District_Grade_BM_PM_Period_Percent_Met

      --Measure level met rates by District
      ,count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) as Measure_Level_Met_District_BM_PM_Period_Total_Students_Assessed
      ,count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) as Measure_Level_Met_District_BM_PM_Period_Total_Students_Enrolled
      ,round(count(distinct b.MCLASS_Student_Number) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure,b.MCLASS_Measure_Level) / (case when count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) = 0 then null 
            else count(distinct b.Student_Number_Schedule) over (partition by b.Academic_Year,b.District,b.Expected_Test,b.MCLASS_Measure) end),4) as Measure_Level_Met_District_BM_PM_Period_Percent

from
(
      select s.Academic_Year
            ,m.District
            ,m.Region
            ,s.School_Level
            ,s.School_ID
            ,m.Reporting_School_ID
            ,s.School
            ,s.School_Abbreviation
            ,s.Student_Number_Enrollment
            ,m.Student_Number_Schedule
            ,s.Student_Name
            ,s.Student_Last_Name
            ,s.Student_First_Name
            ,s.Grade_Level
            ,m.Student_Grade_Level_Schedule
            ,s.OOD
            ,s.Gender
            ,s.Ethnicity
            ,s.Homeless
            ,s.Is_504
            ,s.SPED
            ,s.LEP
            ,s.Economically_Disadvantaged
            ,m.Teacher_ID
            ,m.Teacher_Name
            ,m.Course_Name
            ,m.Course_Number
            ,m.Section_Number
            ,m.Expected_Test
            ,case when m.Student_Number_Schedule is null then 0
                  else 1 end as Enrolled_but_not_Scheduled --Tagging students as enrolled in school but not scheduled for the course that would allow them to take the DIBELS test
            ,case when m.Student_Number_Schedule is not null and d.MCLASS_Student_Number is null then 0
                  else 1 end as Student_has_Assessment_Data --Tagging students who are schedule for the correct class but have not tested yet for the expected assessment term
            ,d.MCLASS_District_Name
            ,d.MCLASS_School_Name
            ,d.MCLASS_Student_Number
            ,case when d.MCLASS_Period in ('BOY','MOY','EOY') then d.MCLASS_Student_Number
                  else null end as MCLASS_Student_Number_BM --Another tag for students who tested for benchmarks
            ,case when d.MCLASS_Period in ('BOY->MOY','MOY->EOY') then d.MCLASS_Student_Number
                  else null end as MCLASS_Student_Number_PM --Another tag for students who tested for progress monitoring
            ,d.MCLASS_Student_Last_Name
            ,d.MCLASS_Student_First_Name
            ,d.MCLASS_Enrollment_Grade
            ,d.MCLASS_Reporting_Class_Name
            ,d.MCLASS_Reporting_Class_ID
            ,d.MCLASS_Official_Teacher_Name
            ,d.MCLASS_Official_Teacher_Staff_ID
            ,d.MCLASS_Assessing_Teacher_Name
            ,d.MCLASS_Assessing_Teacher_Staff_ID
            ,d.MCLASS_Assessment
            ,d.MCLASS_Assessment_Edition
            ,d.MCLASS_Assessment_Grade
            ,d.MCLASS_Period
            ,d.MCLASS_Client_Date
            ,d.MCLASS_Sync_Date
            ,d.MCLASS_Probe_Number
            ,d.MCLASS_Total_Number_of_Probes
            ,d.MCLASS_Measure
            ,cast(d.MCLASS_Measure_Score as string) as MCLASS_Measure_Score
            ,d.MCLASS_Score_Change
            ,d.MCLASS_Measure_Level
            ,d.Measure_Percentile
            ,d.Measure_Semester_Growth
            ,d.Measure_Year_Growth
      from student as s 
      left join schedule as m
      on s.Academic_Year = m.Academic_Year and s.Student_Number_Enrollment = m.Student_Number_Schedule
      left join
      (
            select *
            from benchmark
            union all
            select *
            from progress_monitoring
      ) as d
      on m.Academic_Year = d.MCLASS_Academic_Year and m.Student_Number_Schedule = d.MCLASS_Student_Number and m.Expected_Test = d.MCLASS_Period --This last join on field is to ensure rows are generated for all expected tests, even if the student did not assess for them
) as b
where b.Grade_Level not in ('3','4') --Excluding 3rd and 4th graders until iReady scores are available