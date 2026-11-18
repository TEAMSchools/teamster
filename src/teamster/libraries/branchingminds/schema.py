from pydantic import BaseModel


class AcademicProgressMonitoring(BaseModel):
    school_name: str | None = None
    school_id: str | None = None
    student_name: str | None = None
    student_number: str | None = None
    state_id: str | None = None
    grade_level: str | None = None
    gender: str | None = None
    race_ethnicity: str | None = None
    english_proficiency_level: str | None = None
    gifted_program: str | None = None
    mandated_learning_plan: str | None = None
    ell_status: str | None = None
    subject_area: str | None = None
    assessment_family: str | None = None
    assessment_name: str | None = None
    assessment_grade_level: str | None = None
    score_id: str | None = None
    score: str | None = None
    notes: str | None = None
    staff: str | None = None
    assessment_date: str | None = None
    school_year: str | None = None
    district: str | None = None
    source_file_name: str | None = None


class BenchmarksUniversalScreeners(BaseModel):
    network: str | None = None
    school: str | None = None
    student_name: str | None = None
    student_id: str | None = None
    student_state_id: str | None = None
    grade_level: str | None = None
    race_ethnicity: str | None = None
    gender: str | None = None
    mandated_learning_plan: str | None = None
    gifted_program: str | None = None
    ell_status: str | None = None
    subject_area: str | None = None
    assessment_provider: str | None = None
    assessment: str | None = None
    score: str | None = None
    level: str | None = None
    percentile: str | None = None
    growth_percentile: str | None = None
    description: str | None = None
    staff: str | None = None
    assessment_date: str | None = None
    school_year: str | None = None
    window: str | None = None
    score_id: str | None = None
    student_tags: str | None = None
    district: str | None = None
    source_file_name: str | None = None


class CurrentStudentTierLevels(BaseModel):
    school_name: str | None = None
    school_id: str | None = None
    student_name: str | None = None
    student_number: str | None = None
    state_id: str | None = None
    grade_level: str | None = None
    gender: str | None = None
    race_ethnicity: str | None = None
    english_proficiency_level: str | None = None
    mandated_learning_plan: str | None = None
    gifted_program: str | None = None
    ell_status: str | None = None
    tier_update_id: str | None = None
    subject_area: str | None = None
    tier_level: str | None = None
    tier_update_date: str | None = None
    last_evaluation_date: str | None = None
    tier_update_method: str | None = None
    tier_change_reason: str | None = None
    tier_change_reason_notes: str | None = None
    district: str | None = None
    source_file_name: str | None = None


class DailyInterventionSessions(BaseModel):
    school_name: str | None = None
    school_id: str | None = None
    student_name: str | None = None
    student_number: str | None = None
    state_id: str | None = None
    grade_level: str | None = None
    gender: str | None = None
    race_ethnicity: str | None = None
    english_proficiency_level: str | None = None
    gifted_program: str | None = None
    mandated_learning_plan: str | None = None
    ell_status: str | None = None
    intervention_session_id: str | None = None
    intervention_plan_id: str | None = None
    intervention_name: str | None = None
    intervention_subject_area: str | None = None
    session_week: str | None = None
    session_date: str | None = None
    session_missed_reason: str | None = None
    delivered_minutes_in_session: str | None = None
    planned_minutes_per_session: str | None = None
    planned_sessions_per_week: str | None = None
    intervention_location: str | None = None
    intervention_group_size: str | None = None
    staff_delivering_intervention: str | None = None
    staff_email: str | None = None
    school_year: str | None = None
    district: str | None = None
    source_file_name: str | None = None


class Goals(BaseModel):
    school_name: str | None = None
    school_id: str | None = None
    student_name: str | None = None
    student_number: str | None = None
    state_id: str | None = None
    grade_level: str | None = None
    gender: str | None = None
    race_ethnicity: str | None = None
    english_proficiency_level: str | None = None
    mandated_learning_plan: str | None = None
    gifted_program: str | None = None
    ell_status: str | None = None
    goal_id: str | None = None
    goal_state: str | None = None
    subject_area: str | None = None
    assessment_name: str | None = None
    goal: str | None = None
    goal_score: str | None = None
    goal_status: str | None = None
    staff: str | None = None
    end_date: str | None = None
    school_year: str | None = None
    district: str | None = None
    source_file_name: str | None = None


class InterventionNotes(BaseModel):
    intervention_plan_id: str | None = None
    notes: str | None = None
    notes_date: str | None = None
    district: str | None = None
    source_file_name: str | None = None


class InterventionPlans(BaseModel):
    school_name: str | None = None
    school_id: str | None = None
    student_name: str | None = None
    student_id: str | None = None
    state_id: str | None = None
    grade_level: str | None = None
    gender: str | None = None
    race_ethnicity: str | None = None
    english_proficiency_level: str | None = None
    mandated_learning_plan: str | None = None
    gifted_program: str | None = None
    ell_status: str | None = None
    intervention_name: str | None = None
    intervention_plan_id: str | None = None
    intervention_subject_area: str | None = None
    support_used_as: str | None = None
    support_type: str | None = None
    applicable_tiers: str | None = None
    support_evidence_level: str | None = None
    support_tags: str | None = None
    technology_required: str | None = None
    support_cost: str | None = None
    intervention_frequency: str | None = None
    duration_per_occurrence: str | None = None
    total_minutes_planned: str | None = None
    total_minutes_delivered: str | None = None
    intervention_start_date: str | None = None
    intervention_end_date: str | None = None
    school_year: str | None = None
    intervention_setting: str | None = None
    staff_delivering_intervention: str | None = None
    staff_email: str | None = None
    district: str | None = None
    source_file_name: str | None = None


class NewBehaviorIncidentReport(BaseModel):
    school_name: str | None = None
    school_id: str | None = None
    student_name: str | None = None
    student_id: str | None = None
    state_id: str | None = None
    grade_level: str | None = None
    race_ethnicity: str | None = None
    gender: str | None = None
    mandated_learning_plan: str | None = None
    gifted_program: str | None = None
    english_proficiency_level: str | None = None
    ell_status: str | None = None
    source_incident_id: str | None = None
    brm_incident_id: str | None = None
    source_detail_id: str | None = None
    brm_detail_id: str | None = None
    date: str | None = None
    time: str | None = None
    student_role: str | None = None
    incident_type: str | None = None
    incident_description: str | None = None
    incident_location: str | None = None
    action_taken: str | None = None
    instructional_time_lost: str | None = None
    antecedent: str | None = None
    consequence: str | None = None
    student_account: str | None = None
    deescalation_strategy_student: str | None = None
    deescalation_strategy_staff: str | None = None
    restraint_used: str | None = None
    seclusion_used: str | None = None
    family_notified: str | None = None
    police_notified: str | None = None
    reporting_staff: str | None = None
    reported_date: str | None = None
    data_source: str | None = None
    district: str | None = None
    source_file_name: str | None = None


class Tiers(BaseModel):
    school_name: str | None = None
    school_id: str | None = None
    student_name: str | None = None
    student_number: str | None = None
    state_id: str | None = None
    grade_level: str | None = None
    gender: str | None = None
    race_ethnicity: str | None = None
    english_proficiency_level: str | None = None
    mandated_learning_plan: str | None = None
    gifted_program: str | None = None
    ell_status: str | None = None
    tier_update_id: str | None = None
    subject_area: str | None = None
    tier_level: str | None = None
    tier_update_date: str | None = None
    tier_update_method: str | None = None
    tier_change_reason: str | None = None
    tier_change_reason_notes: str | None = None
    district: str | None = None
    source_file_name: str | None = None
