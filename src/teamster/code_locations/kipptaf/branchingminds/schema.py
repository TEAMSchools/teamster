import json

import py_avro_schema

from teamster.libraries.branchingminds import schema


def _avro_schema(py_type) -> dict:
    return json.loads(
        py_avro_schema.generate(
            py_type=py_type,
            options=(
                py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE
            ),
        )
    )


ACADEMIC_PROGRESS_MONITORING_SCHEMA = _avro_schema(schema.AcademicProgressMonitoring)
BENCHMARKS_UNIVERSAL_SCREENERS_SCHEMA = _avro_schema(
    schema.BenchmarksUniversalScreeners
)
CURRENT_STUDENT_TIER_LEVELS_SCHEMA = _avro_schema(schema.CurrentStudentTierLevels)
DAILY_INTERVENTION_SESSIONS_SCHEMA = _avro_schema(schema.DailyInterventionSessions)
GOALS_SCHEMA = _avro_schema(schema.Goals)
INTERVENTION_NOTES_SCHEMA = _avro_schema(schema.InterventionNotes)
INTERVENTION_PLANS_SCHEMA = _avro_schema(schema.InterventionPlans)
NEW_BEHAVIOR_INCIDENT_REPORT_SCHEMA = _avro_schema(schema.NewBehaviorIncidentReport)
TIERS_SCHEMA = _avro_schema(schema.Tiers)
