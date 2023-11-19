select
    p.*,

    r.record_type_name as record_type_name,
    r.contact_owner_name as counselor_name,
    r.contact_kipp_ms_graduate as is_kipp_ms_graduate,
    r.contact_kipp_hs_graduate as is_kipp_hs_graduate,
    r.contact_current_kipp_student as current_kipp_student,
    r.contact_highest_act_score as highest_act_score,
    r.contact_college_match_display_gpa as college_match_display_gpa,
    r.contact_current_college_cumulative_gpa as current_college_cumulative_gpa,
    r.contact_kipp_region_name as kipp_region_name,
    r.contact_dep_post_hs_simple_admin as post_hs_simple_admin,
    r.contact_currently_enrolled_school as currently_enrolled_school,
    r.contact_ethnicity as ethnicity,
    r.contact_gender as gender,
    r.contact_high_school_graduated_from as high_school_graduated_from,
    r.contact_college_graduated_from as college_graduated_from,
    r.contact_current_college_semester_gpa as current_college_semester_gpa,
    r.contact_middle_school_attended as middle_school_attended,
    r.contact_postsecondary_status as postsecondary_status,
    r.contact_actual_hs_graduation_date as actual_hs_graduation_date,
    r.contact_actual_college_graduation_date as actual_college_graduation_date,
    r.contact_expected_college_graduation as expected_college_graduation_date,

    if(r.contact_most_recent_iep_date is not null, true, false) as is_iep,
    if(r.contact_advising_provider = 'KIPP NYC', true, false) as is_collab,
    case
        when r.contact_college_match_display_gpa >= 3.50
        then '3.50+'
        when r.contact_college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when r.contact_college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when r.contact_college_match_display_gpa >= 2.00
        then '2.00-2.50'
        when r.contact_college_match_display_gpa < 2.00
        then '<2.00'
    end as hs_gpa_bands,

from {{ ref("int_kippadb__persistence") }} as p
left join {{ ref("int_kippadb__roster") }} as r on p.student_number = r.student_number
