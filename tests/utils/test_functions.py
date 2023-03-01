import json

from teamster.core.utils.functions import infer_avro_schema_fields

with open("tests/utils/test.json") as f:
    data = json.load(f)

schema = infer_avro_schema_fields(data)
print()
