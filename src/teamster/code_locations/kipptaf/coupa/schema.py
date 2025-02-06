import json

from py_avro_schema import Option, generate

from teamster.libraries.coupa.schema import Address, User

pas_options = Option.NO_DOC | Option.NO_AUTO_NAMESPACE

ADDRESS_SCHEMA = json.loads(generate(py_type=Address, options=pas_options))

USER_SCHEMA = json.loads(generate(py_type=User, options=pas_options))
