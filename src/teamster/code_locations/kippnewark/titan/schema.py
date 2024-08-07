import json

import py_avro_schema

from teamster.libraries.titan.schema import IncomeFormData, PersonData


class person_data_record(PersonData):
    """helper class for backwards compatibility"""


class income_form_data_record(IncomeFormData):
    """helper class for backwards compatibility"""


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

PERSON_DATA_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=person_data_record, options=pas_options)
)

INCOME_FORM_DATA_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=income_form_data_record, options=pas_options)
)
