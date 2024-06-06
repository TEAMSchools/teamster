from pydantic import BaseModel


class Employee(BaseModel):
    address: str | None = None
    adp_associate_id_clean: str | None = None
    adp_associate_id: str | None = None
    annual_salary: float | None = None
    birth_date: str | None = None
    city: str | None = None
    common_name: str | None = None
    df_employee_number: int | None = None
    employee_s_manager_s_df_emp_number_id: float | None = None
    ethnicity: str | None = None
    file: str | None = None
    first_name: str | None = None
    fivetran_synced: str | None = None
    gender: str | None = None
    grades_taught: str | None = None
    is_manager: str | None = None
    job_family: str | None = None
    jobs_and_positions_flsa_status: str | None = None
    last_name: str | None = None
    legal_entity_name_clean: str | None = None
    legal_entity_name: str | None = None
    line: int | None = None
    mobile_number: str | None = None
    modified: str | None = None
    original_hire_date: str | None = None
    payclass: str | None = None
    paytype: str | None = None
    position_effective_from_date: str | None = None
    position_effective_to_date: str | None = None
    position_title: str | None = None
    postal_code: float | None = None
    preferred_last_name: str | None = None
    primary_job: str | None = None
    primary_on_site_department_clean: str | None = None
    primary_on_site_department_entity: str | None = None
    primary_on_site_department: str | None = None
    primary_site_clean: str | None = None
    primary_site_entity: str | None = None
    primary_site: str | None = None
    rehire_date: str | None = None
    salesforce_id: str | None = None
    state: str | None = None
    status_reason: str | None = None
    status: str | None = None
    subjects_taught: str | None = None
    termination_date: str | None = None


class EmployeeManager(BaseModel):
    app_user_login_id: int | None = None
    application_user_employee_display_name: str | None = None
    description: str | None = None
    employee_display_name: str | None = None
    employee_reference_code: int | None = None
    manager_derived_method: str | None = None
    manager_display_name: str | None = None
    manager_effective_end: str | None = None
    manager_effective_start: str | None = None
    manager_employee_number: int | None = None
    manager_last_modified_timestamp: str | None = None


class EmployeeStatus(BaseModel):
    base_salary: float | None = None
    effective_end: str | None = None
    effective_start: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    number: int | None = None
    status_reason_description: str | None = None
    status: str | None = None


class EmployeeWorkAssignment(BaseModel):
    department_name: str | None = None
    employee_display_name: str | None = None
    employee_reference_code: int | None = None
    flsa_status_name: str | None = None
    job_family_name: str | None = None
    job_name: str | None = None
    legal_entity_name: str | None = None
    pay_class_name: str | None = None
    pay_type_name: str | None = None
    physical_location_name: str | None = None
    primary_work_assignment: bool | None = None
    work_assignment_effective_end: str | None = None
    work_assignment_effective_start: str | None = None
