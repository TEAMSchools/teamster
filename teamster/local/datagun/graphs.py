from dagster import graph

from teamster.core.datagun.graphs import etl_gsheet, etl_sftp


@graph
def gsheets():
    next_year_status = etl_gsheet.alias("next_year_status")
    next_year_status()

    dlm_roster = etl_gsheet.alias("dlm_roster")
    dlm_roster()

    ar_reading_log = etl_gsheet.alias("ar_reading_log")
    ar_reading_log()

    staff_roster = etl_gsheet.alias("staff_roster")
    staff_roster()

    student_roster = etl_gsheet.alias("student_roster")
    student_roster()

    student_contact_info = etl_gsheet.alias("student_contact_info")
    student_contact_info()

    survey_completion = etl_gsheet.alias("survey_completion")
    survey_completion()

    student_logins = etl_gsheet.alias("student_logins")
    student_logins()

    ktc_undermatch_analyis = etl_gsheet.alias("ktc_undermatch_analyis")
    ktc_undermatch_analyis()

    pm_assignment_roster = etl_gsheet.alias("pm_assignment_roster")
    pm_assignment_roster()

    kfwd_contacts = etl_gsheet.alias("kfwd_contacts")
    kfwd_contacts()


@graph
def deanslist():
    college_admission_tests = etl_sftp.alias("college_admission_tests")
    college_admission_tests()

    designations = etl_sftp.alias("designations")
    designations()

    transcript_grades = etl_sftp.alias("transcript_grades")
    transcript_grades()

    finalgrades = etl_sftp.alias("finalgrades")
    finalgrades()

    instructional_tech = etl_sftp.alias("instructional_tech")
    instructional_tech()

    iready_diagnostics = etl_sftp.alias("iready_diagnostics")
    iready_diagnostics()

    iready_lessons = etl_sftp.alias("iready_lessons")
    iready_lessons()

    missing_assignments = etl_sftp.alias("missing_assignments")
    missing_assignments()

    mod_assessment = etl_sftp.alias("mod_assessment")
    mod_assessment()

    mod_standards = etl_sftp.alias("mod_standards")
    mod_standards()

    promo_status = etl_sftp.alias("promo_status")
    promo_status()

    reading_levels = etl_sftp.alias("reading_levels")
    reading_levels()

    sight_words = etl_sftp.alias("sight_words")
    sight_words()

    state_test_scores = etl_sftp.alias("state_test_scores")
    state_test_scores()

    student_misc = etl_sftp.alias("student_misc")
    student_misc()

    transcript_gpas = etl_sftp.alias("transcript_gpas")
    transcript_gpas()


@graph
def illuminate():
    courses = etl_sftp.alias("courses")
    courses()

    enrollment = etl_sftp.alias("enrollment")
    enrollment()

    mastschd = etl_sftp.alias("mastschd")
    mastschd()

    roles = etl_sftp.alias("roles")
    roles()

    roster = etl_sftp.alias("roster")
    roster()

    users = etl_sftp.alias("users")
    users()

    terms = etl_sftp.alias("terms")
    terms()

    student_portal_accounts = etl_sftp.alias("student_portal_accounts")
    student_portal_accounts()

    studemo = etl_sftp.alias("studemo")
    studemo()

    sites = etl_sftp.alias("sites")
    sites()


@graph
def clever():
    students = etl_sftp.alias("students")
    students()

    teachers = etl_sftp.alias("teachers")
    teachers()

    enrollments = etl_sftp.alias("enrollments")
    enrollments()

    staff = etl_sftp.alias("staff")
    staff()

    sections = etl_sftp.alias("sections")
    sections()

    schools = etl_sftp.alias("schools")
    schools()


@graph
def razkids():
    students = etl_sftp.alias("students")
    students()

    teachers = etl_sftp.alias("teachers")
    teachers()


@graph
def read180():
    students = etl_sftp.alias("students")
    students()

    teachers = etl_sftp.alias("teachers")
    teachers()


@graph
def gam():
    students = etl_sftp.alias("students")
    students()

    admins = etl_sftp.alias("admins")
    admins()
