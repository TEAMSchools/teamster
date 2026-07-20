with
    crosswalk_ranking as (
        select distinct x.fs_status_field, x.detailed_status_ranking,
        from {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
        inner join
            {{ ref("int_finalsite__current_academic_year") }} as cy
            on x.file_year = cy.academic_year
    ),

    -- Mirrors the hardcoded status_order CASE in
    -- int_finalsite__status_report_unpivot.sql exactly. Comparing against a
    -- live query of that model's actual rows would miss any fs_status_field
    -- that's declared in the CASE but has never occurred in the data (e.g.
    -- retained_date, which BigQuery's UNPIVOT simply never emits a row for
    -- if every source row's value is NULL) -- this static list is immune to
    -- that, since it reflects the CASE's declaration, not data occurrence.
    unpivot_order as (
        select fs_status_field, status_order,
        from
            unnest(
                [
                    struct('inquiry_date' as fs_status_field, 1 as status_order),
                    ('inquiry_completed_date', 2),
                    ('inactive_inquiry_date', 3),
                    ('applicant_date', 4),
                    ('application_withdrawn_date', 5),
                    ('deferred_date', 6),
                    ('application_complete_date', 7),
                    ('review_in_progress_date', 8),
                    ('waitlisted_date', 9),
                    ('denied_date', 10),
                    ('accepted_date', 11),
                    ('assigned_school_date', 12),
                    ('did_not_enroll_date', 13),
                    ('campus_transfer_requested_date', 14),
                    ('parent_declined_date', 15),
                    ('enrollment_in_progress_date', 16),
                    ('academic_hold_date', 17),
                    ('financial_hold_date', 18),
                    ('not_enrolling_date', 19),
                    ('enrolled_date', 20),
                    ('mid_year_withdrawal_date', 21),
                    ('never_attended_date', 22),
                    ('retained_date', 23),
                    ('summer_withdraw_date', 24)
                ]
            )
    )

select
    c.detailed_status_ranking,

    u.status_order,

    coalesce(c.fs_status_field, u.fs_status_field) as fs_status_field,

from crosswalk_ranking as c
full join unpivot_order as u on c.fs_status_field = u.fs_status_field
where
    c.detailed_status_ranking is null
    or u.status_order is null
    or c.detailed_status_ranking != u.status_order
