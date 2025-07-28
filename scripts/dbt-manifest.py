# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
import csv
import json
import pathlib


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("project")

    args = parser.parse_args()

    path = pathlib.Path("./src/dbt") / args.project / "target/manifest.json"

    manifest = json.loads(s=path.read_text())

    nodes = []
    for _, v in manifest["nodes"].items():
        nodes.append(
            {
                "name": v["name"],
                "resource_type": v["resource_type"],
                "relation_type": v["relation_name"],
                "enabled": v["config"]["enabled"],
            }
        )

    sources = []
    for _, v in manifest["sources"].items():
        sources.append(
            {
                "name": v["name"],
                "resource_type": v["resource_type"],
                "relation_type": v["relation_name"],
                "enabled": v["config"]["enabled"],
            }
        )

    disabled = []
    for _, v in manifest["disabled"].items():
        disabled.append(
            {
                "name": v[0]["name"],
                "resource_type": v[0]["resource_type"],
                "relation_type": v[0]["relation_name"],
                "enabled": v[0]["config"]["enabled"],
            }
        )

    models = nodes + sources + disabled

    with open(f"{args.project}.csv", "w", newline="") as output_file:
        dict_writer = csv.DictWriter(f=output_file, fieldnames=models[0].keys())

        dict_writer.writeheader()
        dict_writer.writerows(models)


if __name__ == "__main__":
    main()
