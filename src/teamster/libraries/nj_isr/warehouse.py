from collections import defaultdict

from google.cloud import bigquery

from teamster.libraries.nj_isr.destinations import REGION_FOLDERS
from teamster.libraries.nj_isr.match import Enrollment, Student

_CROSSWALK_SQL = """
select distinct cast(state_student_id as string) as state_id, student_number,
from `teamster-332318.kipptaf_cambium.int_cambium__all_assessments`
where academic_year = @admin_academic_year and period = 'Spring'
  and student_number is not null
"""

# Both student queries keep to the regions with report folders. The table also
# holds Miami's Focus students, whose student numbers could collide with NJ
# PowerSchool ones; a student now in Miami has no current NJ enrollment and goes
# to the transfer folder.
_STATE_ID_SQL = """
select distinct
    student_number,
    cast(state_studentnumber as string) as state_id,
from `teamster-332318.kipptaf_students.int_students__student_enrollments`
where state_studentnumber is not null
  and region in unnest(@regions)
"""

_ENROLLMENT_SQL = """
select
    student_number,
    academic_year,
    rn_year,
    enroll_status,
    region,
    schoolid,
    school_name,
    last_name,
    first_name,
    dob,
from `teamster-332318.kipptaf_students.int_students__student_enrollments`
where academic_year in (@school_year - 1, @school_year)
  and region in unnest(@regions)
"""


def _regions_parameter() -> bigquery.ArrayQueryParameter:
    return bigquery.ArrayQueryParameter("regions", "STRING", sorted(REGION_FOLDERS))


def load_crosswalk(
    client: bigquery.Client, admin_academic_year: int
) -> dict[str, set[int]]:
    """Map state IDs to student numbers from the spring state test file.

    Args:
        client: BigQuery client.
        admin_academic_year: Academic year of the spring administration, for
            example 2025 for the 2025-26 school year.

    Returns:
        State ID to the set of student numbers recorded for it.
    """
    job = client.query(
        _CROSSWALK_SQL,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "admin_academic_year", "INT64", admin_academic_year
                )
            ]
        ),
    )

    crosswalk = defaultdict[str, set[int]](set)
    for row in job.result():
        crosswalk[row["state_id"]].add(row["student_number"])

    return dict(crosswalk)


def load_students(
    client: bigquery.Client, school_year: int
) -> tuple[dict[int, Student], dict[str, set[int]]]:
    """Load PowerSchool students and the state ID lookup.

    Args:
        client: BigQuery client.
        school_year: Academic year in which the reports are filed. Students
            enrolled in this year or the one before it are returned.

    Returns:
        A tuple of the students by student number and a map from state ID to
        the student numbers PowerSchool holds for it, across all years. Only
        students in a region with report folders are read.
    """
    by_state_id = defaultdict[str, set[int]](set)
    state_id_job = client.query(
        _STATE_ID_SQL,
        job_config=bigquery.QueryJobConfig(query_parameters=[_regions_parameter()]),
    )
    for row in state_id_job.result():
        by_state_id[row["state_id"]].add(row["student_number"])

    job = client.query(
        _ENROLLMENT_SQL,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("school_year", "INT64", school_year),
                _regions_parameter(),
            ]
        ),
    )

    rows_by_student = defaultdict[int, list[bigquery.Row]](list)
    for row in job.result():
        rows_by_student[row["student_number"]].append(row)

    students: dict[int, Student] = {}
    for student_number, rows in rows_by_student.items():
        latest = min(rows, key=lambda r: (-r["academic_year"], r["rn_year"]))

        current_rows = [
            r
            for r in rows
            if r["academic_year"] == school_year
            and r["rn_year"] == 1
            and r["enroll_status"] == 0
        ]
        current = (
            Enrollment(
                region=current_rows[0]["region"],
                schoolid=current_rows[0]["schoolid"],
                school_name=current_rows[0]["school_name"],
            )
            if current_rows
            else None
        )

        last_spring = [
            r["school_name"]
            for r in rows
            if r["academic_year"] == school_year - 1 and r["rn_year"] == 1
        ]

        students[student_number] = Student(
            student_number=student_number,
            last_name=latest["last_name"],
            first_name=latest["first_name"],
            dob=latest["dob"],
            current=current,
            last_spring_school=last_spring[0] if last_spring else None,
        )

    return students, dict(by_state_id)
