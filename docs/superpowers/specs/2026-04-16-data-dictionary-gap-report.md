# Unmatched Staging Columns — Data Dictionary Enrichment Gap Report

Generated from the extraction run against PowerSchool and ADP PDFs. These
columns have no description from the source-system data dictionary. They need
hand-written descriptions or a different source document.

**PowerSchool**: 1495 matched / 2201 YAML columns (67%) **ADP**: 35 matched /
135 YAML columns (25%)

---

## PowerSchool — Extension Tables (KIPP custom, not in PDF)

637 columns across 8 models. These are KIPP-specific custom fields. Descriptions
must be hand-written.

### \`stg_powerschool\_\_s_nj_crs_x\`

- \`ap_course_subject\`
- \`block_schedule_session\`
- \`county_code_override\`
- \`course_level\`
- \`course_sequence_code\`
- \`course_span\`
- \`course_type\`
- \`cte_test_name_code\`
- \`ctecollegecredits\`
- \`ctetestdevelopercode\`
- \`ctetestname\`
- \`district_code_override\`
- \`dual_institution\`
- \`exclude_course_submission_tf\`
- \`nces_course_id\`
- \`nces_subject_area\`
- \`school_code_override\`
- \`sla_include_tf\`

### \`stg_powerschool\_\_s_nj_ren_x\`

- \`alternativeeducationprogram_yn\`
- \`city\`
- \`countycodeattending\`
- \`countycodereceiving\`
- \`countycoderesident\`
- \`cumulativedaysabsent\`
- \`cumulativedayspresent\`
- \`cumulativestateabs\`
- \`daysopen\`
- \`deafhardofhearing_yn\`
- \`declassificationspeddate\`
- \`deviceowner\`
- \`devicetype\`
- \`district_status_override\`
- \`districtcodeattending\`
- \`districtcodereceiving\`
- \`districtcoderesident\`
- \`districtentrydate\`
- \`eligible_for_liep\`
- \`elp_screener_date\`
- \`gifted_and_talented\`
- \`gradelevelcode\`
- \`home_language2\`
- \`home_language3\`
- \`home_language4\`
- \`home_language5\`
- \`home_language_name2\`
- \`home_language_name3\`
- \`home_language_name4\`
- \`home_language_name5\`
- \`homeless_code\`
- \`homelessinstrucservice\`
- \`homelessprimarynighttimeres\`
- \`homelesssupportservice\`
- \`indistrictplacement\`
- \`internetconnectivity\`
- \`languageacquisition\`
- \`learningenvironment\`
- \`lep_completion_date_refused\`
- \`lep_tf\`
- \`lepbegindate\`
- \`lepbegindate2\`
- \`lependdate\`
- \`liep_languageofinstruction\`
- \`liep_parent_refusal_date\`
- \`liep_type\`
- \`liependdate2\`
- \`mddisablingcondition1\`
- \`mddisablingcondition2\`
- \`mddisablingcondition3\`
- \`mddisablingcondition4\`
- \`mddisablingcondition5\`
- \`nonpublic\`
- \`pid_504_tf\`
- \`programtypecode\`
- \`remotedaysabsent\`
- \`remotedayspresent\`
- \`reportedsharedvoc_yn\`
- \`residentmunicipalcode\`
- \`retained_tf\`
- \`schoolcodeattending\`
- \`schoolcodereceiving\`
- \`schoolcoderesident\`
- \`schoolentrydate\`
- \`shared_time_code\`
- \`sid_entrydate\`
- \`sid_excludeenrollment\`
- \`sid_exitdate\`
- \`sld_basic_reading_yn\`
- \`sld_listen_comp_yn\`
- \`sld_math_cal_yn\`
- \`sld_math_prob_solve_yn\`
- \`sld_oral_expresn_yn\`
- \`sld_read_fluency_yn\`
- \`sld_reading_comp_yn\`
- \`sld_writn_exprsn_yn\`
- \`specialed_classification\`
- \`studentslearningmodel\`
- \`titleiindicator\`
- \`titleilanguage_yn\`
- \`titleimath_yn\`
- \`titleiscience_yn\`
- \`tuition_code\`
- \`withdrawal_date\`

### \`stg_powerschool\_\_s_nj_stu_x\`

- \`access_accountablecounty\`
- \`access_accountabledistrict\`
- \`access_accountableschool\`
- \`access_test_format_override\`
- \`access_testingsitecounty\`
- \`access_testingsitedistrict\`
- \`access_testingsiteschool\`
- \`access_tier_paper_tests\`
- \`adulths_nb_credits\`
- \`alternate_access\`
- \`alternativeeducationprogram_yn\`
- \`annual_iep_review_meeting_date\`
- \`ask_specialcodesa\`
- \`ask_specialcodesb\`
- \`ask_specialcodesc\`
- \`ask_specialcodesd\`
- \`asmt_ac\`
- \`asmt_alt_rep_paper\`
- \`asmt_alternate_location\`
- \`asmt_answer_masking\`
- \`asmt_answers_recorded_paper\`
- \`asmt_asl_video\`
- \`asmt_at\`
- \`asmt_braille_response\`
- \`asmt_braille_tactile_paper\`
- \`asmt_bw\`
- \`asmt_closed_caption_ela\`
- \`asmt_color_contrast\`
- \`asmt_dictionary\`
- \`asmt_directions_aloud\`
- \`asmt_directions_clarified\`
- \`asmt_em\`
- \`asmt_emergency_accommodation\`
- \`asmt_es\`
- \`asmt_et\`
- \`asmt_exclude_ela\`
- \`asmt_exclude_math\`
- \`asmt_extended_time\`
- \`asmt_extended_time_math\`
- \`asmt_first_enroll_in_us_school\`
- \`asmt_frequent_breaks\`
- \`asmt_human_signer\`
- \`asmt_humanreader_signer\`
- \`asmt_ih\`
- \`asmt_length_in_ell\`
- \`asmt_lh\`
- \`asmt_math_response\`
- \`asmt_math_response_el\`
- \`asmt_mc\`
- \`asmt_monitor_response\`
- \`asmt_non_screen_reader\`
- \`asmt_ns\`
- \`asmt_ra\`
- \`asmt_rd\`
- \`asmt_read_aloud\`
- \`asmt_refresh_braille_ela\`
- \`asmt_ri\`
- \`asmt_rl\`
- \`asmt_screen_reader\`
- \`asmt_sd\`
- \`asmt_selected_response_ela\`
- \`asmt_small_group\`
- \`asmt_special_equip\`
- \`asmt_specified_area\`
- \`asmt_text_to_speech\`
- \`asmt_time_of_day\`
- \`asmt_unique_accommodation\`
- \`asmt_wd\`
- \`asmt_word_prediction\`
- \`assessmt_ms_accomm_resp\`
- \`biliterate_yn\`
- \`birthplace_refusal\`
- \`block_schedule_session_ela\`
- \`block_schedule_session_math\`
- \`bridge_year\`
- \`calculation_device_math_tools\`
- \`caresactfunds\`
- \`charter_assigned_school\`
- \`charter_date\`
- \`charter_school_loc\`
- \`charter_school_name\`
- \`cityofbirth\`
- \`collegecreditsearned\`
- \`counseling_services_yn\`
- \`countryofbirth\`
- \`countycodeattending\`
- \`countycodereceiving\`
- \`countycoderesident\`
- \`ctecollegecredits\`
- \`ctepostsecondaryinstitution\`
- \`cteprogramofstudy_yn\`
- \`cteprogramstatus\`
- \`ctesingleparentstatus_yn\`
- \`ctetestdevelopercode\`
- \`ctetestname\`
- \`ctetestskillassesment\`
- \`ctewblearning\`
- \`cteworkbasedlearning\`
- \`cumdaysinmembershipaddto_tf\`
- \`cumdayspresentaddto_tf\`
- \`cumdaystowardtruancyaddto_tf\`
- \`cumulativedaysabsent\`
- \`cumulativedaysinmembership\`
- \`cumulativedayspresent\`
- \`cumulativedaystowardtruancy\`
- \`cumulativestateabs\`
- \`datelastleadtest\`
- \`datelastmedexam\`
- \`dateofpolioimmun\`
- \`daysopen\`
- \`deafhardofhearing_yn\`
- \`declassificationspeddate\`
- \`determined_ineligible_yn\`
- \`deviceowner\`
- \`devicetype\`
- \`district_status_override\`
- \`district_studentid\`
- \`districtcodeattending\`
- \`districtcodereceiving\`
- \`districtcoderesident\`
- \`districttimeless1year_yn\`
- \`early_intervention_yn\`
- \`eighthtechlit\`
- \`eligibility_determ_date\`
- \`eligible_for_liep\`
- \`elp_screener_date\`
- \`embedded_co_writer_ela\`
- \`eoc_title1biology_tf\`
- \`examiner_smid\`
- \`examinersmid1\`
- \`examinersmid2\`
- \`examinersmid3\`
- \`examinersmid4\`
- \`examinersmid5\`
- \`family_care_release_yn\`
- \`federalhsmathtestingreq\`
- \`firstentrydateintoausschool\`
- \`firsthsmathassessment_yn\`
- \`former_iep\`
- \`generationcodesuffix\`
- \`gifted_and_talented\`
- \`gradelevelcode\`
- \`graduation_pathway_ela\`
- \`graduation_pathway_math\`
- \`healthinsprovider\`
- \`healthinsstatus_yn\`
- \`home_language\`
- \`home_language2\`
- \`home_language3\`
- \`home_language4\`
- \`home_language5\`
- \`home_language_name\`
- \`home_language_name2\`
- \`home_language_name3\`
- \`home_language_name4\`
- \`home_language_name5\`
- \`homelessinstrucservice\`
- \`homelessprimarynighttimeres\`
- \`homelesssupportservice\`
- \`iep_begin_date\`
- \`iep_end_date\`
- \`iep_exemptpassingbiology_tf\`
- \`iep_exemptpassinglal_tf\`
- \`iep_exemptpassingmath_tf\`
- \`iep_exempttakingbiology_tf\`
- \`iep_exempttakinglal_tf\`
- \`iep_exempttakingmath_tf\`
- \`iep_level\`
- \`iepgradcourserequirement\`
- \`iepgraduationattendance\`
- \`immigrantstatus_yn\`
- \`includeinassareport_tf\`
- \`includeinctereport_tf\`
- \`includeinnjsmart_tf\`
- \`includeinstucourse_tf\`
- \`indistrictplacement\`
- \`initial_iep_meeting_date\`
- \`initial_process_delay_reason\`
- \`internetconnectivity\`
- \`languageacquisition\`
- \`leadlevel\`
- \`learningenvironment\`
- \`lep_completion_date_refused\`
- \`lep_tf\`
- \`lepbegindate\`
- \`lepbegindate2\`
- \`lependdate\`
- \`liep_classification\`
- \`liep_data\`
- \`liep_languageofinstruction\`
- \`liep_parent_refusal_date\`
- \`liep_refusal\`
- \`liep_type\`
- \`liependdate2\`
- \`lunchstatusoverride\`
- \`math_state_assessment_name\`
- \`mddisablingcondition1\`
- \`mddisablingcondition2\`
- \`mddisablingcondition3\`
- \`mddisablingcondition4\`
- \`mddisablingcondition5\`
- \`migrant_tf\`
- \`military_connected_indicator\`
- \`native_language\`
- \`nces_course_id\`
- \`nces_subject_area\`
- \`nonpublic\`
- \`occupational_therapy_serv_yn\`
- \`other_related_services_yn\`
- \`parcc_braille_paper\`
- \`parcc_class_name_override_ela\`
- \`parcc_class_name_override_math\`
- \`parcc_constructed_response_ela\`
- \`parcc_ela_test_code\`
- \`parcc_ell_paper_accom\`
- \`parcc_examiner_smid_ela\`
- \`parcc_examiner_smid_math\`
- \`parcc_exempt_from_passing\`
- \`parcc_iep_paper_accom\`
- \`parcc_large_print_paper\`
- \`parcc_math_test_code\`
- \`parcc_math_tools\`
- \`parcc_reader_signer_for_paper\`
- \`parcc_retest\`
- \`parcc_sec504_paper_accom\`
- \`parcc_session_location_ela\`
- \`parcc_session_location_math\`
- \`parcc_staff_smid_override_ela\`
- \`parcc_staff_smid_override_math\`
- \`parcc_student_identifier\`
- \`parcc_test_format\`
- \`parcc_testing_site_county\`
- \`parcc_testing_site_district\`
- \`parcc_testing_site_school\`
- \`parcc_text_to_speech\`
- \`parcc_text_to_speech_math\`
- \`parcc_translation_math_paper\`
- \`parent_consent_intial_iep_date\`
- \`parent_consent_obtain_code\`
- \`parental_consent_eval_date\`
- \`physical_therapy_services_yn\`
- \`pid_504_tf\`
- \`pid_accommodations_a_tf\`
- \`pid_accommodations_b_tf\`
- \`pid_accommodations_c_tf\`
- \`pid_accommodations_d_tf\`
- \`pid_apalangartsliteracy_tf\`
- \`pid_apamath_tf\`
- \`pid_apascience_tf\`
- \`pid_apatestingcds\`
- \`pid_audioamplification\`
- \`pid_brailletest_yn\`
- \`pid_classroom\`
- \`pid_computerassisted\`
- \`pid_contentareatutoring_yn\`
- \`pid_contentbasedesl_yn\`
- \`pid_developbilingual_yn\`
- \`pid_heritagelanguage_yn\`
- \`pid_inclusionarysupport_yn\`
- \`pid_largeprint_yn\`
- \`pid_lepexemptlal_tf\`
- \`pid_lowvisionaids\`
- \`pid_madetape_tf\`
- \`pid_modifiedtestdirections\`
- \`pid_nativelang\`
- \`pid_noadditionalservices_yn\`
- \`pid_notapplicable_yn\`
- \`pid_otherapproved\`
- \`pid_outofdistplacement_tf\`
- \`pid_outresidenceplacement_tf\`
- \`pid_parentalrefusal_yn\`
- \`pid_presentationformat\`
- \`pid_pullout_yn\`
- \`pid_pulloutesl_yn\`
- \`pid_scribedresponse_yn\`
- \`pid_selfcontained_yn\`
- \`pid_sendingcds\`
- \`pid_settingformat\`
- \`pid_shelteredenginstruct_yn\`
- \`pid_shortsegmenttestadmin_tf\`
- \`pid_structengimmersion_yn\`
- \`pid_supplementaleduserv\`
- \`pid_testformat\`
- \`pid_timeinlep2\`
- \`pid_timingscheduling\`
- \`pid_title1langartslit_tf\`
- \`pid_title1math_tf\`
- \`pid_title1science_tf\`
- \`pid_title3status\`
- \`pid_transbilingual_yn\`
- \`pid_twowayimmersion_yn\`
- \`presentation\`
- \`primarycipcode\`
- \`programtypecode\`
- \`proofofage\`
- \`reevaluation_date\`
- \`referral_date\`
- \`remotedaysabsent\`
- \`remotedaysmembership\`
- \`remotedayspresent\`
- \`remotelearninghelpline_yn\`
- \`remotepercentageofday\`
- \`reportedsharedvoc_yn\`
- \`residentmunicipalcode\`
- \`retained_tf\`
- \`school_disabled\`
- \`schoolcodeattending\`
- \`schoolcodereceiving\`
- \`schoolcoderesident\`
- \`schooltimeless1year_yn\`
- \`science_test_name\`
- \`secondary_disability\`
- \`shared_time_code\`
- \`sid_entrydate\`
- \`sid_excludeenrollment\`
- \`sid_exitdate\`
- \`sla_accountable_site_county\`
- \`sla_accountable_site_district\`
- \`sla_accountable_site_school\`
- \`sla_alt_rep_paper\`
- \`sla_alternate_location\`
- \`sla_answer_masking\`
- \`sla_answers_recorded_paper\`
- \`sla_asl_video\`
- \`sla_braille_response\`
- \`sla_braille_tactile_paper\`
- \`sla_class_name_override\`
- \`sla_closed_caption\`
- \`sla_color_contrast\`
- \`sla_constructed_response\`
- \`sla_dictionary\`
- \`sla_directions_aloud\`
- \`sla_directions_clarified\`
- \`sla_emergency_accommodation\`
- \`sla_examiner_smid\`
- \`sla_exclude_tf\`
- \`sla_extended_time\`
- \`sla_frequent_breaks\`
- \`sla_human_signer\`
- \`sla_humanreader_signer\`
- \`sla_large_print_paper\`
- \`sla_monitor_response\`
- \`sla_non_screen_reader\`
- \`sla_read_aloud\`
- \`sla_refresh_braille\`
- \`sla_retest\`
- \`sla_science_response_el\`
- \`sla_screen_reader\`
- \`sla_selected_response\`
- \`sla_session_loc_override\`
- \`sla_small_group\`
- \`sla_spanish_trans\`
- \`sla_special_equip\`
- \`sla_specified_area\`
- \`sla_staffoverride_smid\`
- \`sla_test_code\`
- \`sla_test_format\`
- \`sla_testing_site_county\`
- \`sla_testing_site_district\`
- \`sla_testing_site_school\`
- \`sla_text_to_speech\`
- \`sla_time_of_day\`
- \`sla_unique_accommodation\`
- \`sla_word_prediction\`
- \`sld_basic_reading_yn\`
- \`sld_listen_comp_yn\`
- \`sld_math_cal_yn\`
- \`sld_math_prob_solve_yn\`
- \`sld_oral_expresn_yn\`
- \`sld_read_fluency_yn\`
- \`sld_reading_comp_yn\`
- \`sld_writn_exprsn_yn\`
- \`speassessmentparticipant_yn\`
- \`speassignmentsubmissions_yn\`
- \`special_education_placement\`
- \`special_status\`
- \`specialed_classification\`
- \`specoachingorcheckin_yn\`
- \`spedtier\`
- \`speech_lang_theapy_services_yn\`
- \`speechtotextwordprediction\`
- \`speelectroniccomm_yn\`
- \`speonlinelearningplatforms\`
- \`speother_yn\`
- \`spesynchonlineclass_yn\`
- \`state_assessment_name\`
- \`state_ell_status\`
- \`state_lep_status\`
- \`stateofbirth\`
- \`student_type\`
- \`studentslearningmodel\`
- \`stureporting_name\`
- \`supplementaleduserv\`
- \`time_in_regular_program\`
- \`title1_status_tf\`
- \`titleiindicator\`
- \`titleilanguage_yn\`
- \`titleimath_yn\`
- \`titleiscience_yn\`
- \`tiv_serv_aide_tf\`
- \`tiv_serv_assist_tf\`
- \`tiv_serv_extyear_tf\`
- \`tiv_serv_ind_instr_tf\`
- \`tiv_serv_indnursing_tf\`
- \`tiv_serv_intensive_tf\`
- \`tiv_serv_interpreter_tf\`
- \`tiv_serv_pupil_tf\`
- \`tiv_serv_resplacement_tf\`
- \`tuition_code\`
- \`typeofearnedcollegecredits\`
- \`typeofworkbasedlearning\`
- \`withdrawal_date\`
- \`worldlang_assessed1\`
- \`worldlang_assessed1_name\`
- \`worldlang_assessed2\`
- \`worldlang_assessed2_name\`
- \`worldlang_assessed3\`
- \`worldlang_assessed3_name\`
- \`worldlang_assessed4\`
- \`worldlang_assessed4_name\`
- \`worldlang_assessed5\`
- \`worldlang_assessed5_name\`
- \`worldlang_assessment1\`
- \`worldlang_assessment2\`
- \`worldlang_assessment3\`
- \`worldlang_assessment4\`
- \`worldlang_assessment5\`

### \`stg_powerschool\_\_s_nj_usr_x\`

- \`excl_frm_smart_stf_submissn\`
- \`formername\`
- \`generationcodesuffix\`
- \`local_teacher_id\`
- \`smart_alternaterouteprog\`
- \`smart_certificationstatus\`
- \`smart_districtbegindate\`
- \`smart_districtentrycode\`
- \`smart_districtexitdate\`
- \`smart_districtexitreason\`
- \`smart_ellinstructorcredtype\`
- \`smart_employmentsepatyp\`
- \`smart_employmentstatus\`
- \`smart_first_name\`
- \`smart_highestleveled\`
- \`smart_languagespoken\`
- \`smart_last_name\`
- \`smart_mepsessiontype\`
- \`smart_migrantedprogramcat\`
- \`smart_nameprefix\`
- \`smart_nationalboardaward\`
- \`smart_salary\`
- \`smart_seprogramcontrcat\`
- \`smart_stafcompenanualsup\`
- \`smart_stafcompnsatnbassal\`
- \`smart_titleiprogramcat\`
- \`smart_traditionalrouteprog\`
- \`smart_yearsinlea\`
- \`smart_yearsinnj\`
- \`smart_yearsofexp\`
- \`staffmemberid\`

### \`stg_powerschool\_\_s_stu_x\`

- \`activedutyparent\`
- \`barrierintaccess\`
- \`birthcity\`
- \`birthcountry\`
- \`birthcounty\`
- \`birthstate\`
- \`careertechedu_yn\`
- \`careerworkreadiness_yn\`
- \`clgcareerreadiness_yn\`
- \`comctzn_yn\`
- \`contact_email\`
- \`contact_fname\`
- \`contact_lname\`
- \`contact_phone\`
- \`county\`
- \`deviceaccess\`
- \`devicetype\`
- \`economicdisadvantage\`
- \`entrydateintousschool\`
- \`excludefromedfi\`
- \`fafsa\`
- \`foster_care\`
- \`graduation_class_rank\`
- \`healthid\`
- \`home_language\`
- \`immigrant\`
- \`internetaccess\`
- \`internetinresidence\`
- \`internetperformance\`
- \`jobcorps\`
- \`luncheligibility\`
- \`maiden_name\`
- \`maritalstatus\`
- \`native_language\`
- \`ontracktograduate\`
- \`outofdistrict_distoverride\`
- \`parentrefusalofimmaccuracy\`
- \`postsecedu_yn\`
- \`pref_first\`
- \`pref_last\`
- \`pref_middle\`
- \`priorityforservice\`
- \`privateschool\`
- \`programenddate\`
- \`programstartdate\`
- \`repeatgradeindicator\`
- \`reportedvalue\`
- \`residencystatus\`
- \`schoolchoicetransfer\`
- \`sealofbiliteracy\`
- \`section504_yn\`
- \`singleparent\`
- \`steamstemparticipant\`
- \`suffix\`
- \`tribal_affiliation_1\`
- \`tribal_affiliation_2\`
- \`tribal_affiliation_3\`
- \`tribal_affiliation_sif_1\`
- \`tribal_affiliation_sif_2\`
- \`tribal_affiliation_sif_3\`
- \`twentyfirstcenturyserved\`
- \`virtualstudent\`
- \`youthchallenge\`

### \`stg_powerschool\_\_u_clg_et_stu\`

- \`exit_code\`
- \`exit_date\`
- \`id\`
- \`when_modified_or_created\`

### \`stg_powerschool\_\_u_clg_et_stu_alt\`

- \`exit_code\`
- \`exit_date\`
- \`id\`
- \`when_modified_or_created\`

### \`stg_powerschool\_\_u_storedgrades_de\`

- \`de_course_name\`
- \`de_institution\`
- \`de_pass_yn\`
- \`de_score\`
- \`de_semester\`
- \`id\`

---

## PowerSchool — Derived Columns (added in staging SQL)

35 columns across 12 models. These are computed in the staging SQL, not from the
PowerSchool database. Descriptions should reference the transformation logic.

- \`stg_powerschool\_\_calendar_day\`: \`week_end_date\`, \`week_start_date\`
- \`stg_powerschool\_\_cc\`: \`academic_year\`, \`fiscal_year\`, \`yearid\`
- \`stg_powerschool\_\_log\`: \`\_dbt_source_relation\`, \`academic_year\`
- \`stg_powerschool\_\_pgfinalgrades\`: \`grade_adjusted\`, \`percent_decimal\`,
  \`percent_decimal_adjusted\`
- \`stg_powerschool\_\_schools\`: \`school_level\`
- \`stg_powerschool\_\_spenrollments\`: \`academic_year\`, \`is_current\`,
  \`rn_student_program_year_desc\`
- \`stg_powerschool\_\_storedgrades\`: \`\_dbt_source_relation\`,
  \`academic_year\`, \`agg_credittype\`, \`fiscal_year\`,
  \`gradescale_name_unweighted\`, \`is_transfer_grade\`, \`percent_decimal\`,
  \`storecode_type\`, \`yearid\`
- \`stg_powerschool\_\_studentcorefields\`: \`is_homeless\`
- \`stg_powerschool\_\_students\`: \`ethnicity_code\`, \`gender_code\`
- \`stg_powerschool\_\_termbins\`: \`is_current_term\`, \`semester\`,
  \`storecode_order\`, \`storecode_type\`
- \`stg_powerschool\_\_terms\`: \`academic_year\`, \`fiscal_year\`, \`semester\`
- \`stg_powerschool\_\_users\`: \`\_dbt_source_relation\`,
  \`dagster_code_location\`

---

## PowerSchool — Core Unmatched (likely in PDF but parser missed)

48 columns across 18 models. These columns are likely in the PDF data dictionary
but the parser could not match them due to column-name formatting differences.

### \`stg_powerschool\_\_attendance_conversion_items\`

- \`daypartid\`

### \`stg_powerschool\_\_cc\`

- \`abs_sectionid\`
- \`abs_termid\`

### \`stg_powerschool\_\_gpprogresssubject\`

- \`issummation\`
- \`nodetype\`
- \`testnodepassed\`

### \`stg_powerschool\_\_gradecalculationtype\`

- \`ismulticategoryeditable\`

### \`stg_powerschool\_\_gradeschoolconfig\`

- \`iscitizenshipdisplayed\`
- \`isgradescaleteachereditable\`
- \`ismulticategoryallowed\`
- \`ismulticategoryeditable\`
- \`issectstndweighteditable\`
- \`lockwarningoffset\`
- \`minimumassignmentvalue\`

### \`stg_powerschool\_\_gradesectionconfig\`

- \`isgradescaleteachereditable\`
- \`issectstndweighteditable\`
- \`minimumassignmentvalue\`

### \`stg_powerschool\_\_roledef\`

- \`productname\`

### \`stg_powerschool\_\_schools\`

- \`fee_exemption_status\`

### \`stg_powerschool\_\_schoolstaff\`

- \`sched_usehouse\`

### \`stg_powerschool\_\_sections\`

- \`att_mode_code\`
- \`exclude_ada\`
- \`excludefromclassrank\`
- \`excludefromhonorroll\`
- \`parent_section_id\`
- \`section_number\`
- \`section_type\`

### \`stg_powerschool\_\_storedgrades\`

- \`ab_course_eva_pro_cd\`
- \`ab_pri_del_met_cd\`
- \`comment_value\`

### \`stg_powerschool\_\_student_email\`

- \`email\`

### \`stg_powerschool\_\_studentcorefields\`

- \`c_504_information\`
- \`ipt_oral_curdate\`

### \`stg_powerschool\_\_students\`

- \`customrank_gpa\`
- \`exclude_fr_rank\`
- \`gradreqsetid\`
- \`ldapenabled\`
- \`studentpers_guid\`
- \`studentpict_guid\`

### \`stg_powerschool\_\_teachercategory\`

- \`defaultscoreentrypoints\`

### \`stg_powerschool\_\_termbins\`

- \`currentgrade\`

### \`stg_powerschool\_\_test\`

- \`alpha_entry_type\`
- \`historical_test\`
- \`number_entry_type\`
- \`percent_entry_type\`
- \`teacher_access\`

### \`stg_powerschool\_\_users\`

- \`adminldapenabled\`
- \`teacherldapenabled\`

---

## ADP — Unmatched Columns

100 columns across 1 models. Most are derived columns added in staging SQL or
deeply nested struct fields not individually documented in the ADP API guide.

### \`stg_adp_workforce_now\_\_workers\`

- \`associate_oid\`
- \`effective_date_end\`
- \`effective_date_end_timestamp\`
- \`effective_date_start\`
- \`effective_date_start_timestamp\`
- \`is_current_record\`
- \`is_prestart\`
- \`language_code\_\_code_value\`
- \`language_code\_\_effective_date\`
- \`language_code\_\_long_name\`
- \`language_code\_\_short_name\`
- \`person\_\_birth_date\`
- \`person**birth_name**formatted_name\`
- \`person**birth_name**generation_affix_code\_\_code_value\`
- \`person**birth_name**generation_affix_code\_\_effective_date\`
- \`person**birth_name**generation_affix_code\_\_long_name\`
- \`person**birth_name**generation_affix_code\_\_short_name\`
- \`person**birth_name**given_name\`
- \`person**birth_name**middle_name\`
- \`person**birth_name**nick_name\`
- \`person**birth_name**qualification_affix_code\_\_code_value\`
- \`person**birth_name**qualification_affix_code\_\_effective_date\`
- \`person**birth_name**qualification_affix_code\_\_long_name\`
- \`person**birth_name**qualification_affix_code\_\_short_name\`
- \`person\_\_disabled_indicator\`
- \`person**ethnicity_code**effective_date\`
- \`person\_\_ethnicity_code_name\`
- \`person\_\_family_name_1\`
- \`person**gender_code**effective_date\`
- \`person**gender_code**long_name\`
- \`person\_\_gender_code_name\`
- \`person**gender_self_identity_code**effective_date\`
- \`person**gender_self_identity_code**long_name\`
- \`person\_\_given_name\`
- \`person**highest_education_level_code**effective_date\`
- \`person**legal_address**country_subdivision_level_1\_\_code_value\`
- \`person**legal_address**country_subdivision_level_1\_\_effective_date\`
- \`person**legal_address**country_subdivision_level_1\_\_long_name\`
- \`person**legal_address**country_subdivision_level_1\_\_short_name\`
- \`person**legal_address**country_subdivision_level_1\_\_subdivision_type\`
- \`person**legal_address**country_subdivision_level_2\_\_code_value\`
- \`person**legal_address**country_subdivision_level_2\_\_effective_date\`
- \`person**legal_address**country_subdivision_level_2\_\_long_name\`
- \`person**legal_address**country_subdivision_level_2\_\_short_name\`
- \`person**legal_address**country_subdivision_level_2\_\_subdivision_type\`
- \`person**legal_address**item_id\`
- \`person**legal_address**line_one\`
- \`person**legal_address**line_three\`
- \`person**legal_address**line_two\`
- \`person**legal_address**name_code\_\_code_value\`
- \`person**legal_address**name_code\_\_effective_date\`
- \`person**legal_address**name_code\_\_long_name\`
- \`person**legal_address**name_code\_\_short_name\`
- \`person**legal_address**type_code\_\_code_value\`
- \`person**legal_address**type_code\_\_effective_date\`
- \`person**legal_address**type_code\_\_long_name\`
- \`person**legal_address**type_code\_\_short_name\`
- \`person**legal_name**generation_affix_code\_\_code_value\`
- \`person**legal_name**generation_affix_code\_\_effective_date\`
- \`person**legal_name**generation_affix_code\_\_long_name\`
- \`person**legal_name**generation_affix_code\_\_short_name\`
- \`person**legal_name**nick_name\`
- \`person**legal_name**qualification_affix_code\_\_code_value\`
- \`person**legal_name**qualification_affix_code\_\_effective_date\`
- \`person**legal_name**qualification_affix_code\_\_long_name\`
- \`person**legal_name**qualification_affix_code\_\_short_name\`
- \`person**marital_status_code**effective_date\`
- \`person**marital_status_code**long_name\`
- \`person\_\_military_discharge_date\`
- \`person**military_status_code**code_value\`
- \`person**military_status_code**effective_date\`
- \`person**military_status_code**long_name\`
- \`person**military_status_code**short_name\`
- \`person**preferred_gender_pronoun_code**effective_date\`
- \`person**preferred_name**formatted_name\`
- \`person**preferred_name**generation_affix_code\_\_code_value\`
- \`person**preferred_name**generation_affix_code\_\_effective_date\`
- \`person**preferred_name**generation_affix_code\_\_long_name\`
- \`person**preferred_name**generation_affix_code\_\_short_name\`
- \`person**preferred_name**nick_name\`
- \`person**preferred_name**qualification_affix_code\_\_code_value\`
- \`person**preferred_name**qualification_affix_code\_\_effective_date\`
- \`person**preferred_name**qualification_affix_code\_\_long_name\`
- \`person**preferred_name**qualification_affix_code\_\_short_name\`
- \`person**race_code**effective_date\`
- \`person**race_code**identification_method_code\_\_code_value\`
- \`person**race_code**identification_method_code\_\_effective_date\`
- \`person**race_code**identification_method_code\_\_long_name\`
- \`person**race_code**identification_method_code\_\_short_name\`
- \`person\_\_race_code_name\`
- \`person\_\_tobacco_user_indicator\`
- \`race_ethnicity_reporting\`
- \`worker_dates\_\_termination_date\`
- \`worker_hire_date_recent\`
- \`worker_id**scheme_code**code_value\`
- \`worker_id**scheme_code**effective_date\`
- \`worker_id**scheme_code**long_name\`
- \`worker_id**scheme_code**short_name\`
- \`worker_status**status_code**code_value_lag\`
- \`worker_status**status_code**effective_date\`

---

## Summary

| Category                   | Columns | Models | Action                                  |
| -------------------------- | ------- | ------ | --------------------------------------- |
| PS Extension (KIPP custom) | 637     | 8      | Hand-write descriptions                 |
| PS Derived                 | 35      | 12     | Describe from staging SQL logic         |
| PS Core unmatched          | 48      | 18     | Manual PDF lookup or parser improvement |
| ADP unmatched              | 100     | 1      | Describe from staging SQL or API docs   |
| **Total unmatched**        | **820** |        |                                         |
