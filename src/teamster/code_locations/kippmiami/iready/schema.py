import json

import py_avro_schema

from teamster.libraries.iready.schema import (
    DiagnosticInstruction,
    DiagnosticResults,
    InstructionalUsage,
    PersonalizedInstruction,
)


class diagnostic_and_instruction_record(DiagnosticInstruction):
    """helper classes for backwards compatibility"""


class diagnostic_results_record(DiagnosticResults):
    """helper classes for backwards compatibility"""


class instructional_usage_data_record(InstructionalUsage):
    """helper classes for backwards compatibility"""


class personalized_instruction_by_lesson_record(PersonalizedInstruction):
    """helper classes for backwards compatibility"""


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE


DIAGNOSTIC_AND_INSTRUCTION_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=diagnostic_and_instruction_record, options=pas_options
    )
)

DIAGNOSTIC_RESULTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=diagnostic_results_record, options=pas_options)
)

INSTRUCTIONAL_USAGE_DATA_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=instructional_usage_data_record, options=pas_options
    )
)

PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=personalized_instruction_by_lesson_record, options=pas_options
    )
)
