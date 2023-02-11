import requests
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

for child in children:
    title = child["title"]
    link = child["link"]

    if link == "'/PSDD/powerschool-tables/auditing-tables-fields'":
        continue

    child_page = requests.get(f"{base_url}{link}")
    soup = BeautifulSoup(markup=child_page.text, features="html.parser")
    print()
