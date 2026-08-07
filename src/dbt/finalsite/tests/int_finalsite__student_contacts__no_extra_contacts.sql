{{ config(severity="warn") }}

-- A student with more parents than the two conventional slots. Anything past
-- contact_2 is emitted here; the receivers exclude those slots themselves
-- (the contacts pivot and ParentSquare by construction, DeansList and the
-- contacts bridge via an explicit slot filter) rather than the row being
-- dropped upstream of this model. Warn so the count stays visible; matching
-- `contact_%` rather than a literal catches a fourth slot too.
select finalsite_enrollment_id, contact_slot,
from {{ ref("int_finalsite__student_contacts") }}
where contact_slot like 'contact\\_%' and contact_slot not in ('contact_1', 'contact_2')
