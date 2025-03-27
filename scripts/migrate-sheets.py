import json

with open(file="src/dbt/kipptaf/target/manifest.json") as fp:
    manifest = json.load(fp=fp)

google_sheets = []

sources = manifest["sources"]

for source in sources.values():
    external = source["external"] or {}

    options = external.get("options") or {}

    if options.get("format") == "GOOGLE_SHEETS":
        google_sheets.append(source)

sql = [
    # trunk-ignore(bandit/B608)
    f"""create or replace table
    kipptaf_appsheet.{gs["name"].replace("src_", "")} as (
    select *, from {gs["schema"].replace("z_dev_", "")}.{gs["name"]}
);
"""
    for gs in google_sheets
]

with open(file="src/dbt/kipptaf/bq-migrate-gsheets.sql", mode="w") as f:
    f.write("".join(sql))

print()
