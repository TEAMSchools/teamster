import json

from py_avro_schema import Option, generate

from teamster.libraries.knowbe4.schema import Enrollment

pas_options = Option.NO_DOC | Option.NO_AUTO_NAMESPACE

ENROLLMENT_SCHEMA = json.loads(generate(py_type=Enrollment, options=pas_options))
