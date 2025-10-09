with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "schoolmint_grow", "src_schoolmint_grow__observations"
                ),
                partition_by="_id",
                order_by="_dagster_partition_date desc",
            )
        }}
    ),

    observations as (
        select
            dd._id as observation_id,
            dd.`name`,
            dd.assignactionstepwidgettext as assign_action_step_widget_text,
            dd.district,
            dd.isprivate as is_private,
            dd.ispublished as is_published,
            dd.locked,
            dd.observationmodule as observation_module,
            dd.observationtag1 as observation_tag_1,
            dd.observationtag2 as observation_tag_2,
            dd.observationtag3 as observation_tag_3,
            dd.observationtype as observation_type,
            dd.privatenotes1 as private_notes_1,
            dd.privatenotes2 as private_notes_2,
            dd.privatenotes3 as private_notes_3,
            dd.privatenotes4 as private_notes_4,
            dd.quickhits as quick_hits,
            dd.requiresignature as require_signature,
            dd.score,
            dd.scoreaveragedbystrand as score_averaged_by_strand,
            dd.sendemail as send_email,
            dd.sharednotes1 as shared_notes_1,
            dd.sharednotes2 as shared_notes_2,
            dd.sharednotes3 as shared_notes_3,
            dd.signed,

            /* records */
            dd.rubric._id as rubric_id,
            dd.rubric.`name` as rubric_name,

            dd.observer._id as observer_id,
            dd.observer.email as observer_email,
            dd.observer.`name` as observer_name,

            dd.teacher._id as teacher_id,
            dd.teacher.email as teacher_email,
            dd.teacher.`name` as teacher_name,

            dd.teachingassignment._id as teaching_assignment_id,
            dd.teachingassignment.course as teaching_assignment_course,
            dd.teachingassignment.grade as teaching_assignment_grade,
            dd.teachingassignment.gradelevel as teaching_assignment_grade_level,
            dd.teachingassignment.`period` as teaching_assignment_period,
            dd.teachingassignment.school as teaching_assignment_school,

            dd.tagnotes1.notes as tag_notes_1_notes,
            dd.tagnotes1.tags as tag_notes_1_tags,

            dd.tagnotes2.notes as tag_notes_2_notes,
            dd.tagnotes2.tags as tag_notes_2_tags,

            dd.tagnotes3.notes as tag_notes_3_notes,
            dd.tagnotes3.tags as tag_notes_3_tags,

            dd.tagnotes4.notes as tag_notes_4_notes,
            dd.tagnotes4.tags as tag_notes_4_tags,

            /* repeated */
            dd.comments,
            dd.eventlog as event_log,
            dd.files,
            dd.listtwocolumna as list_two_column_a,
            dd.listtwocolumnapaired as list_two_column_a_paired,
            dd.listtwocolumnb as list_two_column_b,
            dd.listtwocolumnbpaired as list_two_column_b_paired,
            dd.meetings,
            dd.tags,

            /* repeated records */
            dd.magicnotes as magic_notes,
            dd.observationscores as observation_scores,

            cast(dd.archivedat as timestamp) as archived_at,
            cast(dd.created as timestamp) as created,
            cast(dd.firstpublished as timestamp) as first_published,
            cast(dd.lastmodified as timestamp) as last_modified,
            cast(dd.lastpublished as timestamp) as last_published,
            cast(dd.observedat as timestamp) as observed_at,
            cast(dd.observeduntil as timestamp) as observed_until,
            cast(dd.signedat as timestamp) as signed_at,
            cast(dd.viewedbyteacher as timestamp) as viewed_by_teacher,

            date(
                cast(dd.observedat as timestamp), '{{ var("local_timezone") }}'
            ) as observed_at_date_local,

            array_to_string(dd.listtwocolumna, '|') as list_two_column_a_str,
            array_to_string(dd.listtwocolumnb, '|') as list_two_column_b_str,

            nullif(
                array_to_string(array(select mn.text, from dd.magicnotes as mn), '; '),
                ''
            ) as magic_notes_text,
        from deduplicate as dd
        where dd._dagster_partition_archived = 'f'
    )

select
    *,

    {{
        date_to_fiscal_year(
            date_field="observed_at_date_local", start_month=7, year_source="start"
        )
    }} as academic_year,
from observations
