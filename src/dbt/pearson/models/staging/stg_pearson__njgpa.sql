select
    accountabledistrictcode as `accountable_district_code`,
    accountableorganizationaltype as `accountable_organizational_type`,
    accountableschoolcode as `accountable_school_code`,
    birthdate as `birth_date`,
    federalraceethnicity as `federal_race_ethnicity`,
    gradelevelwhenassessed as `grade_level_when_assessed`,
    localstudentidentifier as `local_student_identifier`,
    nottestedreason as `not_tested_reason`,
    shipreportdistrictcode as `ship_report_district_code`,
    shipreportschoolcode as `ship_report_school_code`,
    specialeducationplacement as `special_education_placement`,
    staffmemberidentifier as `staff_member_identifier`,
    statestudentidentifier as `state_student_identifier`,
    testadministrator as `test_administrator`,
    testingdistrictcode as `testing_district_code`,
    testingorganizationaltype as `testing_organizational_type`,
    testingschoolcode as `testing_school_code`,
    testscorecomplete as `test_score_complete`,
    texttospeech as `text_to_speech`,
    timeofday as `time_of_day`,
    totaltestitemsattempted as `total_test_items_attempted`,
    unit1numberofattempteditems as `unit1_number_of_attempted_items`,
    unit1onlinetestenddatetime as `unit1_online_test_end_date_time`,
    unit1onlineteststartdatetime as `unit1_online_test_start_date_time`,
    unit1totaltestitems as `unit1_total_test_items`,
    unit2numberofattempteditems as `unit2_number_of_attempted_items`,
    unit2onlinetestenddatetime as `unit2_online_test_end_date_time`,
    unit2onlineteststartdatetime as `unit2_online_test_start_date_time`,
    unit2totaltestitems as `unit2_total_test_items`,

    americanindianoralaskanative as `american_indian_or_alaska_native`,
    asian as `asian`,
    blackorafricanamerican as `black_or_african_american`,
    hispanicorlatinoethnicity as `hispanic_or_latino_ethnicity`,
    nativehawaiianorotherpacificislander as `native_hawaiian_or_other_pacific_islander`,
    twoormoreraces as `two_or_more_races`,
    white as `white`,

    economicdisadvantagestatus as `economic_disadvantage_status`,
    homeless as `homeless`,
    migrantstatus as `migrant_status`,
    englishlearnerel as `english_learner_el`,

    firsthighschoolmathassessment as `first_high_school_math_assessment`,
    nottestedcode as `not_tested_code`,
    retest as `retest`,
    summativeflag as `summative_flag`,
    testattemptednessflag as `test_attemptedness_flag`,

    elaconstructedresponse as `ela_constructed_response`,
    elaselectedresponseortechnologyenhanceditems
    as `ela_selected_response_or_technology_enhanced_items`,
    elaccommodation as `el_accommodation`,
    elexemptfromtakingela as `el_exempt_from_taking_ela`,
    frequentbreaks as `frequent_breaks`,
    iepexemptfrompassing as `iep_exempt_from_passing`,
    mathematicsscienceaccommodatedresponse
    as `mathematics_science_accommodated_response`,
    separatealternatelocation as `separate_alternate_location`,
    smallgrouptesting as `small_group_testing`,
    specifiedareaorsetting as `specified_area_or_setting`,
    studentreadsassessmentaloudtoself as `student_reads_assessment_aloudto_self`,
    uniqueaccommodation as `unique_accommodation`,
    wordtoworddictionaryenglishnativelanguage
    as `word_to_word_dictionary_english_native_language`,

    nullif(accountabledistrictname, '') as `accountable_district_name`,
    nullif(accountableschoolname, '') as `accountable_school_name`,
    nullif(testingdistrictname, '') as `testing_district_name`,
    nullif(testingschoolname, '') as `testing_school_name`,
    nullif(assessmentyear, '') as `assessment_year`,
    nullif(assessmentgrade, '') as `assessment_grade`,
    nullif(subject, '') as `subject`,
    nullif(period, '') as `period`,
    nullif(testadministration, '') as `test_administration`,
    nullif(testcode, '') as `test_code`,
    nullif(teststatus, '') as `test_status`,
    nullif(firstname, '') as `first_name`,
    nullif(middlename, '') as `middle_name`,
    nullif(lastorsurname, '') as `last_or_surname`,
    nullif(gender, '') as `gender`,
    nullif(reportsuppressionaction, '') as `report_suppression_action`,
    nullif(reportsuppressioncode, '') as `report_suppression_code`,
    nullif(voidscorecode, '') as `void_score_code`,
    nullif(voidscorereason, '') as `void_score_reason`,

    nullif(
        administrationdirectionsclarifiedinstudentsnativelanguage, ''
    ) as `administration_directions_clarified_in_students_native_language`,
    nullif(
        administrationdirectionsreadaloudinstudentsnativelanguage, ''
    ) as `administration_directions_read_aloud_in_students_native_language`,
    nullif(
        alternaterepresentationpapertest, ''
    ) as `alternate_representation_paper_test`,
    nullif(answermasking, '') as `answer_masking`,
    nullif(answersrecordedintestbooklet, '') as `answers_recordedin_test_booklet`,
    nullif(aslvideo, '') as `asl_video`,
    nullif(
        assistivetechnologynonscreenreader, ''
    ) as `assistive_technology_non_screen_reader`,
    nullif(assistivetechnologyscreenreader, '') as `assistive_technology_screen_reader`,
    nullif(batteryformid, '') as `battery_form_id`,
    nullif(braillewithtactilegraphics, '') as `braille_with_tactile_graphics`,
    nullif(
        calculationdeviceandmathematicstools, ''
    ) as `calculation_device_and_mathematics_tools`,
    nullif(classname, '') as `class_name`,
    nullif(closedcaptioningforela, '') as `closed_captioning_for_ela`,
    nullif(colorcontrast, '') as `color_contrast`,
    nullif(datefirstenrolledinusschool, '') as `date_first_enrolledin_us_school`,
    nullif(electronicbrailleresponse, '') as `electronic_braille_response`,
    nullif(emergencyaccommodation, '') as `emergency_accommodation`,
    nullif(
        englishlearneraccommodatedresponses, ''
    ) as `english_learner_accommodated_responses`,
    nullif(extendedtime, '') as `extended_time`,
    nullif(formeriep, '') as `former_iep`,
    nullif(home_language, '') as `home_language`,
    nullif(humanreaderorhumansigner, '') as `human_reader_or_human_signer`,
    nullif(humansignerfortestdirections, '') as `human_signer_for_test_directions`,
    nullif(largeprint, '') as `large_print`,
    nullif(monitortestresponse, '') as `monitor_test_response`,
    nullif(multipletestregistration, '') as `multiple_test_registration`,
    nullif(njelstatus, '') as `njel_status`,
    nullif(njnotattemptflag, '') as `nj_not_attempt_flag`,
    nullif(onlinepcr1, '') as `online_pcr1`,
    nullif(onlinepcr2, '') as `online_pcr2`,
    nullif(primarydisabilitytype, '') as `primary_disability_type`,
    nullif(refreshablebrailledisplay, '') as `refreshable_braille_display`,
    nullif(rosterflag, '') as `roster_flag`,
    nullif(spanishtransadaptation, '') as `spanish_transadaptation`,
    nullif(specializedequipmentorfurniture, '') as `specialized_equipment_or_furniture`,
    nullif(speechtotextandwordprediction, '') as `speechto_textand_word_prediction`,
    nullif(studentwithdisabilities, '') as `student_with_disabilities`,
    nullif(
        subclaim1categoryifnotattempted, ''
    ) as `subclaim1_category_if_not_attempted`,
    nullif(
        subclaim2categoryifnotattempted, ''
    ) as `subclaim2_category_if_not_attempted`,
    nullif(
        subclaim3categoryifnotattempted, ''
    ) as `subclaim3_category_if_not_attempted`,
    nullif(
        subclaim4categoryifnotattempted, ''
    ) as `subclaim4_category_if_not_attempted`,
    nullif(
        subclaim5categoryifnotattempted, ''
    ) as `subclaim5_category_if_not_attempted`,
    nullif(
        testcsemprobablerangeifnotattempted, ''
    ) as `test_csem_probable_range_if_not_attempted`,
    nullif(
        testperformancelevelifnotattempted, ''
    ) as `test_performance_level_if_not_attempted`,
    nullif(testreadingcsemifnotattempted, '') as `test_reading_csem_if_not_attempted`,
    nullif(
        testreadingscalescoreifnotattempted, ''
    ) as `test_reading_scale_score_if_not_attempted`,
    nullif(testscalescoreifnotattempted, '') as `test_scale_score_if_not_attempted`,
    nullif(testwritingcsemifnotattempted, '') as `test_writing_csem_if_not_attempted`,
    nullif(
        testwritingscalescoreifnotattempted, ''
    ) as `test_writing_scale_score_if_not_attempted`,
    nullif(unit1formid, '') as `unit1_form_id`,
    nullif(unit2formid, '') as `unit2_form_id`,
    nullif(unit3formid, '') as `unit3_form_id`,
    nullif(unit3numberofattempteditems, '') as `unit3_number_of_attempted_items`,
    nullif(unit3onlinetestenddatetime, '') as `unit3_online_test_end_date_time`,
    nullif(unit3onlineteststartdatetime, '') as `unit3_online_test_start_date_time`,
    nullif(unit3totaltestitems, '') as `unit3_total_test_items`,
    nullif(wordprediction, '') as `word_prediction`,

    nullif(studentuuid, '') as `student_uuid`,
    nullif(studenttestuuid, '') as `student_test_uuid`,
    nullif(studentunit1testuuid, '') as `student_unit1_test_uuid`,
    nullif(studentunit2testuuid, '') as `student_unit2_test_uuid`,
    nullif(studentunit3testuuid, '') as `student_unit3_test_uuid`,
    nullif(studentassessmentidentifier, '') as `student_assessment_identifier`,
from {{ source("pearson", "src_pearson__njgpa") }}
where summativeflag and testattemptednessflag
