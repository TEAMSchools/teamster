import re

import pandas
import requests
import yaml
from bs4 import BeautifulSoup

base_url = "https://docs.powerschool.com"
current_link = "/PSDD/powerschool-tables"

children_json = requests.get(
    url=f"{base_url}/rest/scroll-viewport/1.0/tree/children",
    params={
        "viewportId": "AC1F27F50166C0F19A2425124E700A70",
        "root": "/PSDD",
        "parent": "/PSDD",
        "current": current_link,
    },
).json()

children = [
    child["children"]
    for child in children_json
    if child["title"] == "PowerSchool Tables"
][0]

models = []
for child in children:
    link = child["link"]
    print(link)
    if link in ["/PSDD/powerschool-tables/auditing-tables-fields"]:
        continue

    child_page = requests.get(f"{base_url}{link}")

    soup = BeautifulSoup(markup=child_page.text, features="lxml")

    # parse columns table
    cols_table_tag = soup.find("table")
    if cols_table_tag:
        dfs = pandas.read_html(str(cols_table_tag))

        # convert table to dict
        cols_table = dfs[0]
        cols = cols_table.to_dict(orient="records")
        for col in cols:
            columns = {
                "name": col["Column Name"].lower(),
                "description": col["Description"],
                "meta": {
                    "Initial Version": (
                        col.get("Initial Version") or col.get("Initial Versoin")
                    ),
                    "Oracle Data Type": col.get("Data Type") or col.get("Type"),
                },
            }
    else:
        columns = None

    title_match = re.match(r"^([\w\s\$]+)(,\s\d+|\s)?\(?(.*)?$", child["title"])
    table_name, table_id, table_version = title_match.groups()

    models.append(
        {
            "name": f"stg_powerschool__{table_name.lower()}",
            "description": f"{soup.find('p').text}<br><br>Table ID: {table_id}<br>{table_version}",
            "columns": columns,
        }
    )

with open("powerschool/models/staging/models.yml", "w") as f:
    yaml.safe_dump(data={"version": 2, "models": models}, stream=f)
