from pydantic import BaseModel, Field


class StudentTracker(BaseModel):
    class_level: str | None = None
    college_code_branch: str | None = None
    college_name: str | None = None
    college_sequence: str | None = None
    college_state: str | None = None
    degree_cip_1: str | None = None
    degree_cip_2: str | None = None
    degree_cip_3: str | None = None
    degree_cip_4: str | None = None
    degree_major_1: str | None = None
    degree_major_2: str | None = None
    degree_major_3: str | None = None
    degree_major_4: str | None = None
    degree_title: str | None = None
    enrollment_begin: str | None = None
    enrollment_cip_1: str | None = None
    enrollment_cip_2: str | None = None
    enrollment_end: str | None = None
    enrollment_major_1: str | None = None
    enrollment_major_2: str | None = None
    enrollment_status: str | None = None
    first_name: str | None = None
    graduated: str | None = None
    graduation_date: str | None = None
    last_name: str | None = None
    middle_initial: str | None = None
    name_suffix: str | None = None
    public_private: str | None = None
    record_found_y_n: str | None = None
    requester_return_field: str | None = None
    search_date: str | None = None
    your_unique_identifier: str | None = None
    source_file_name: str | None = None

    two_year_four_year: str | None = Field(None, alias="2_year_4_year")
