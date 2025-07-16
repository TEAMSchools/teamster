import json

import py_avro_schema

from teamster.libraries.iready.schema import (
    DiagnosticInstruction,
    DiagnosticResults,
    InstructionalUsage,
    InstructionByLesson,
    PersonalizedInstruction,
)

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

DIAGNOSTIC_AND_INSTRUCTION_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=DiagnosticInstruction, options=pas_options)
)

DIAGNOSTIC_RESULTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=DiagnosticResults, options=pas_options)
)

INSTRUCTIONAL_USAGE_DATA_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=InstructionalUsage, options=pas_options)
)

PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=PersonalizedInstruction, options=pas_options)
)

INSTRUCTION_BY_LESSON_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=InstructionByLesson, options=pas_options)
)
