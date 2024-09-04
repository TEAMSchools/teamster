with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("deanslist", "src_deanslist__incidents"),
                partition_by="IncidentID",
                order_by="_file_name desc",
            )
        }}
    ),

    incidents_clean as (
        select
            hearingflag as hearing_flag,
            isactive as is_active,
            isreferral as is_referral,
            sendalert as send_alert,

            /* records */
            closets.timezone_type as close_ts_timezone_type,
            createts.timezone_type as create_ts_timezone_type,
            dl_lastupdate.timezone_type as dl_last_update_timezone_type,
            hearingdate.timezone_type as hearing_date_timezone_type,
            issuets.timezone_type as issue_ts_timezone_type,
            returndate.timezone_type as return_date_timezone_type,
            reviewts.timezone_type as review_ts_timezone_type,
            updatets.timezone_type as update_ts_timezone_type,

            /* repeated records */
            actions,
            custom_fields,
            penalties,

            /* transformations */
            nullif(addlreqs, '') as addl_reqs,
            nullif(adminsummary, '') as admin_summary,
            nullif(category, '') as category,
            nullif(context, '') as context,
            nullif(createby, '') as create_by,
            nullif(createfirst, '') as create_first,
            nullif(createlast, '') as create_last,
            nullif(createmiddle, '') as create_middle,
            nullif(createtitle, '') as create_title,
            nullif(familymeetingnotes, '') as family_meeting_notes,
            nullif(followupnotes, '') as followup_notes,
            nullif(gender, '') as gender,
            nullif(gradelevelshort, '') as grade_level_short,
            nullif(hearinglocation, '') as hearing_location,
            nullif(hearingnotes, '') as hearing_notes,
            nullif(hearingtime, '') as hearing_time,
            nullif(homeroomname, '') as homeroom_name,
            nullif(infraction, '') as infraction,
            nullif(`location`, '') as `location`,
            nullif(reporteddetails, '') as reported_details,
            nullif(returnperiod, '') as return_period,
            nullif(`status`, '') as `status`,
            nullif(studentfirst, '') as student_first,
            nullif(studentlast, '') as student_last,
            nullif(studentmiddle, '') as student_middle,
            nullif(updateby, '') as update_by,
            nullif(updatefirst, '') as update_first,
            nullif(updatelast, '') as update_last,
            nullif(updatemiddle, '') as update_middle,
            nullif(updatetitle, '') as update_title,

            safe_cast(nullif(incidentid, '') as int) as incident_id,
            safe_cast(nullif(categoryid, '') as int) as category_id,
            safe_cast(nullif(createstaffschoolid, '') as int) as create_staff_school_id,
            safe_cast(nullif(infractiontypeid, '') as int) as infraction_type_id,
            safe_cast(nullif(locationid, '') as int) as location_id,
            safe_cast(nullif(reportingincidentid, '') as int) as reporting_incident_id,
            safe_cast(nullif(schoolid, '') as int) as school_id,
            safe_cast(nullif(statusid, '') as int) as status_id,
            safe_cast(nullif(studentid, '') as int) as student_id,
            safe_cast(nullif(studentschoolid, '') as int) as student_school_id,
            safe_cast(nullif(updatestaffschoolid, '') as int) as update_staff_school_id,

            nullif(closets.timezone, '') as close_ts_timezone,
            nullif(createts.timezone, '') as create_ts_timezone,
            nullif(dl_lastupdate.timezone, '') as dl_last_update_timezone,
            nullif(hearingdate.timezone, '') as hearing_date_timezone,
            nullif(issuets.timezone, '') as issue_ts_timezone,
            nullif(returndate.timezone, '') as return_date_timezone,
            nullif(reviewts.timezone, '') as review_ts_timezone,
            nullif(updatets.timezone, '') as update_ts_timezone,

            safe_cast(nullif(closets.date, '') as datetime) as close_ts_date,
            safe_cast(nullif(createts.date, '') as datetime) as create_ts_date,
            safe_cast(nullif(hearingdate.date, '') as datetime) as hearing_date_date,
            safe_cast(nullif(issuets.date, '') as datetime) as issue_ts_date,
            safe_cast(nullif(returndate.date, '') as datetime) as return_date_date,
            safe_cast(nullif(reviewts.date, '') as datetime) as review_ts_date,
            safe_cast(nullif(updatets.date, '') as datetime) as update_ts_date,
            safe_cast(
                nullif(dl_lastupdate.date, '') as datetime
            ) as dl_last_update_date,
        from deduplicate
        where isactive
    )

select
    *,

    {{
        teamster_utils.date_to_fiscal_year(
            date_field="create_ts_date", start_month=7, year_source="start"
        )
    }} as create_ts_academic_year,
from incidents_clean
