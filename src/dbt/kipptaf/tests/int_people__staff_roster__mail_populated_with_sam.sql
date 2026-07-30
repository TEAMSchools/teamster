-- Anyone with a sam_account_name must also have a mail value, or they lose
-- self-access at the Entra cutover, when USERNAME() starts returning email
-- instead of the AD username the Tableau permissions block compares today.
select sr.employee_number,
from {{ ref("int_people__staff_roster") }} as sr
where
    sr.assignment_status != 'Terminated'
    and sr.sam_account_name is not null
    and sr.mail is null
