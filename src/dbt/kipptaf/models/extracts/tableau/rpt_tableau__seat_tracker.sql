select 
s.academic_year,
s.adp_dept,
s.adp_location,
s.display_name as job_title,
s.entity,
s.grade_band,
s.short_name as location,
s.mid_year_hire as is_mid_year_hire,
s.plan_status,
s.staffing_status,
s.status_detail,
s.staffing_model_id,

srr.preferred_name_lastfirst as recruiter,
srr.report_to_preferred_name_lastfirst as recruiter_manager,
srt.preferred_name_lastfirst as teammate,

if(s.staffing_status='Open',true,false) as is_open_seat,
if(s.status_detail IN ('New Hire','Transfer In'),true,false) as is_new_hire,
if(s.staffing_status='Staffed',true,false) as is_staffed,
if(s.plan_status = 'Active',true,false) as is_active,

from {{ ref("stg_people__seats") }} as s
/* recruiters */
left join {{ ref('base_people__staff_roster') }} as srr
on s.teammate = srr.employee_number
/* all staff */
left join {{ ref('base_people__staff_roster') }} as srt
on s.teammate = srt.employee_number
where academic_year is not null
