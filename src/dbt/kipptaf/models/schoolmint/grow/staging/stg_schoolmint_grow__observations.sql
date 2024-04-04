with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "schoolmint_grow", "src_schoolmint_grow__observations"
                ),
                partition_by="_id",
                order_by="_file_name desc",
            )
        }}
    )

select
    _id as `observation_id`,
    `name` as `name`,
    assignactionstepwidgettext as `assign_action_step_widget_text`,
    district as `district`,
    isprivate as `is_private`,
    ispublished as `is_published`,
    locked as `locked`,
    observationmodule as `observation_module`,
    observationtag1 as `observation_tag_1`,
    observationtag2 as `observation_tag_2`,
    observationtag3 as `observation_tag_3`,
    observationtype as `observation_type`,
    privatenotes1 as `private_notes_1`,
    privatenotes2 as `private_notes_2`,
    privatenotes3 as `private_notes_3`,
    privatenotes4 as `private_notes_4`,
    quickhits as `quick_hits`,
    requiresignature as `require_signature`,
    score as `score`,
    scoreaveragedbystrand as `score_averaged_by_strand`,
    sendemail as `send_email`,
    sharednotes1 as `shared_notes_1`,
    sharednotes2 as `shared_notes_2`,
    sharednotes3 as `shared_notes_3`,
    signed as `signed`,
    safe_cast(archivedat as timestamp) as `archived_at`,
    safe_cast(created as timestamp) as `created`,
    safe_cast(firstpublished as timestamp) as `first_published`,
    safe_cast(lastmodified as timestamp) as `last_modified`,
    safe_cast(lastpublished as timestamp) as `last_published`,
    safe_cast(observedat as timestamp) as `observed_at`,
    safe_cast(observeduntil as timestamp) as `observed_until`,
    safe_cast(signedat as timestamp) as `signed_at`,
    safe_cast(viewedbyteacher as timestamp) as `viewed_by_teacher`,

    {# repeated #}
    meetings as `meetings`,
    tags as `tags`,
    comments as `comments`,
    listtwocolumna as `list_two_column_a`,
    listtwocolumnapaired as `list_two_column_a_paired`,
    listtwocolumnb as `list_two_column_b`,
    listtwocolumnbpaired as `list_two_column_b_paired`,
    eventlog as `event_log`,
    files as `files`,

    {# records #}
    rubric._id as `rubric_id`,
    rubric.name as `rubric_name`,
    observer._id as `observer_id`,
    observer.email as `observer_email`,
    observer.name as `observer_name`,
    teacher._id as `teacher_id`,
    teacher.email as `teacher_email`,
    teacher.name as `teacher_name`,
    teachingassignment._id as `teaching_assignment_id`,
    teachingassignment.course as `teaching_assignment_course`,
    teachingassignment.grade as `teaching_assignment_grade`,
    teachingassignment.gradelevel as `teaching_assignment_grade_level`,
    teachingassignment.period as `teaching_assignment_period`,
    teachingassignment.school as `teaching_assignment_school`,
    tagnotes1.notes as `tag_notes_1_notes`,
    tagnotes1.tags as `tag_notes_1_tags`,
    tagnotes2.notes as `tag_notes_2_notes`,
    tagnotes2.tags as `tag_notes_2_tags`,
    tagnotes3.notes as `tag_notes_3_notes`,
    tagnotes3.tags as `tag_notes_3_tags`,
    tagnotes4.notes as `tag_notes_4_notes`,
    tagnotes4.tags as `tag_notes_4_tags`,

    {# repeated records #}
    observationscores as `observation_scores`,
    magicnotes as `magic_notes`,
    videonotes as `video_notes`,
    attachments as `attachments`,
    videos as `videos`,
from deduplicate
where _dagster_partition_archived = 'f'
