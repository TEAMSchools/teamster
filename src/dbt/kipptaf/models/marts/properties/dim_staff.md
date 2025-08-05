{% docs teammate_assignment_status %}

The employment status of a teammate (also known as an employee).
This dimension is frequently used to filter staff for analysis, such as counting only 'Active' employees.
Available status are: 'Active', 'Leave', 'Deceased', and 'Terminated'.
'Active' employees are currently employed and not on leave.
'Leave' employees are currently employed but on a leave and not on the job.
'Deceased' employees are excluded from all counts and analyses.
'Terminated' employees are not currently employed.

{% enddocs %}

{% docs teammate_race_ethnicity_reporting %}

The race or ethnicity of an employee, based on self-reported data and grouped. Used in DEI reporting and filtering by demographic groups.
Employees can multi-select race/ethnicities so the total count of race/ethnicities can by higher than the count of staff.
Values include 'Asian', 'Black/African American', 'Latinx/Hispanic', 'White', and 'Bi/Multiracial'.
Some employees also have null values which means they haven't provided data, or selected "Decline to State" or "Race/Ethnicity Not Listed", those are typically grouped as one when filtering.

{% enddocs %}

{% docs teammate_entity %}

Our organization is made up of four entities, also called business units or regions.
'KIPP TEAM and Family Schools Inc', the charter management organization for three other entities
'TEAM Academy Charter School', which operates schools in Newark, New Jersey region,
'KIPP Cooper Norcross Academy' which operates schools in the Camden, New Jersey region, and
'KIPP Miami', which operates schools in the Miami, Florida region.
Used to group staff by organizational structure and business unit.

{% enddocs %}

{% docs teammate_location %}

This is the physical location where the employee/teammate works. We have 19 active school locations with names like
"KIPP TEAM Academy" and "KIPP Lanning Square Primary", and three administrative locations which begin with the word "Room"
(Room 9 for the entity TEAM Academy Charter School/Newark region, Room 10 for KIPP Cooper Norcross Academy/Camden region, and Room 11 for KIPP Miami/Miami region), which is where the staff that serve multiple schools or the whole district/network work.

{% enddocs %}

{% docs teammate_grade_band %}

Schools are divided into three grade bands:
ES: Elementary or Primary schools (typically grades Kindergarten - 4)
MS: Middle Schools (typically grades 5 - 8)
HS: High Schools (typically grades 9 - 12).
Kids in grade 9 are called Freshman, 10 are sophomores, 11 are juniors, and 12 are seniors in high school.

{% enddocs %}

{% docs teammate_department %}

The department the employee/teammate belongs to. In schools this is sometimes the subject area they teach, like 'Science', 'Math' or 'ELA', which stands for English/Language arts.
Outside of schools are departments that serve many schools like 'Data', 'Technology', and 'Talent'.
Commonly used to filter staff to see how they are allocated across departments.
{% enddocs %}

{% docs teammate_job_title %}
The formal title of the employee's current position as entered in ADP, our Human Resources Information System.
Examples: 'Teacher', 'Assistant Principal', 'Director of Operations', 'Custodian', 'Systems Analyst'.
Useful for filtering by role type and in conjunction with the field is_teacher which groups several titles into
a category to denote someone with a role teaching in the classroom.

{% enddocs %}

{% docs teammate_manager %}
The employee/teammate's formal manager as entered in ADP, our Human Resources Information System. For instructional roles,
this person is often called a the teacher's 'coach'.
Used to group or filter staff by reporting structure and analyze coaching loads.
Example question: "How many teachers does this Assistant Principal coach?" is the same as
"For how many employees/teammates is this person listed as the manager?"

{% enddocs %}

{% docs teammate_original_hire_date %}
The date the employee was first hired by KIPP, regardless of whether they left and came back at any point in time.
Used to track tenure, calculate years of service, and measure long-term staff trends.

{% enddocs %}

{% docs teammate_work_assignment_actual_start_date %}
The date the employee began their current assignment or role. For instructional employees, these typically start at the beginning of a new school year.
Our academic years run from July to June, and we use the year of the July date as the academic year. Example: March 2026 is in the 2025 academic year.
Useful for measuring assignment duration or transitions.

{% enddocs %}

{% docs teammate_is_teacher %}
A boolean field to note whether someone is in a role where they teach in the classroom.
We tend to group certain roles as "teacher" although the official job title may vary. This indicator includes
all teammates/employees in these roles: 'Teacher','Teacher in Residence','ESE Teacher', 'Teacher ESL', 'Teacher in Residence ESL' and 'Learning Specialist'.
Used to count the number of teammates in classroom instructional roles.

{% enddocs %}
