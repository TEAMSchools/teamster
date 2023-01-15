from fastavro import parse_schema, writer

data = [
    {
        "null": None,
        "boolean": True,
        "int": 1,
        "float": 3.14,
        "string": "spam",
        "bytes": b"eggs",
    },
    {
        # "null": None,
        "boolean": True,
        "int": 1,
        "float": 3.14,
        "string": "spam",
        "bytes": b"eggs",
    },
]

fields = []
for column in set().union(*(d.keys() for d in data)):
    field = {"name": column, "type": ["null", "string"]}
    fields.append(field)

parsed_schema = parse_schema({"type": "record", "name": "data", "fields": fields})

data_file_path = "test.avro"
for i, d in enumerate(data):
    if i == 0:
        with open(data_file_path, "wb") as f:
            writer(f, parsed_schema, [d])
    else:
        with open(data_file_path, "a+b") as f:
            writer(f, parsed_schema, [d])

print()
