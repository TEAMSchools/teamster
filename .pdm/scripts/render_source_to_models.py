import pathlib

import yaml
from jinja2 import BaseLoader, Environment

model_sql = """
{% raw %}{{{% endraw %}
    dbt_utils.union_relations(
        relations=[
            source(
                "kippnewark_powerschool", "{{ model_name }}"
            ),
            source(
                "kippcamden_powerschool", "{{ model_name }}"
            ),
            source(
                "kippmiami_powerschool", "{{ model_name }}"
            ),
        ]
    )
{% raw %}}}{% endraw %}
"""

template = Environment(loader=BaseLoader).from_string(source=model_sql)

source_filepath = pathlib.Path("kipptaf/models/powerschool/sources.yml")

with source_filepath.open(mode="r") as f:
    source_yaml = yaml.safe_load(stream=f)

all_tables = set()

for source in source_yaml["sources"]:
    tables = source["tables"]

    for table in tables:
        all_tables.add(table["name"])

model_dir = source_filepath.parent / "staging"

model_dir.mkdir(parents=True, exist_ok=True)

for model in all_tables:
    model_filepath = model_dir / f"{model}.sql"

    rendered_string = template.render(model_name=model)

    with model_filepath.open(mode="w+") as f:
        f.write(rendered_string)
