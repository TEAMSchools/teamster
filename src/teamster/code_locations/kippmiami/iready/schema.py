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

ASSET_SCHEMA = {
    "diagnostic_and_instruction": json.loads(
        py_avro_schema.generate(
            py_type=diagnostic_and_instruction_record, options=pas_options
        )
    ),
    "diagnostic_results": json.loads(
        py_avro_schema.generate(py_type=diagnostic_results_record, options=pas_options)
    ),
    "instructional_usage_data": json.loads(
        py_avro_schema.generate(
            py_type=instructional_usage_data_record, options=pas_options
        )
    ),
    "personalized_instruction_by_lesson": json.loads(
        py_avro_schema.generate(
            py_type=personalized_instruction_by_lesson_record, options=pas_options
        )
    ),
}
