# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
import json
import re
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("command")
    parser.add_argument("project")
    parser.add_argument("select", nargs="*")
    parser.add_argument("--full-refresh", action="store_true")
    parser.add_argument("--prod", action="store_true")

    args = parser.parse_args()

    if args.command == "help":
        subprocess.run(args=["/workspaces/teamster/.venv/bin/dbt", "-h"])
    elif args.command == "sxs":
        cloud_storage_uri_base = (
            "gs://teamster-"
            + (args.project if args.prod else "test")
            + f"/dagster/{args.project}"
        )

        run_args = [
            "/workspaces/teamster/.venv/bin/dbt",
            "run-operation",
            "stage_external_sources",
            f"--project-dir=src/dbt/{args.project}",
            f"--vars={{'ext_full_refresh': 'true', 'cloud_storage_uri_base': '{cloud_storage_uri_base}'}}",
        ]

        if args.select:
            run_args.extend(["--args", " ".join(["select:", *args.select])])

        subprocess.run(args=run_args)
    elif args.command == "yaml":
        select = args.select[0]

        output_split = subprocess.check_output(
            args=[
                "/workspaces/teamster/.venv/bin/dbt",
                "list",
                f"--project-dir=src/dbt/{args.project}",
                "--resource-type",
                "model",
                "--select",
                select,
                "--output",
                "name",
            ]
        ).split(b"\n")

        model_names = [
            o.decode()
            for o in output_split
            if re.match(pattern=r"(\w+)", string=o.decode())
        ]

        run_args = [
            "/workspaces/teamster/.venv/bin/dbt",
            "run-operation",
            "generate_model_yaml",
            f"--project-dir=src/dbt/{args.project}",
            "--args",
            json.dumps({"model_names": model_names}),
        ]

        yaml = subprocess.check_output(args=run_args).decode()

        with open("properties.yml", "w") as f:
            f.write(yaml)
    else:
        run_args = [
            "/workspaces/teamster/.venv/bin/dbt",
            args.command,
            f"--project-dir=src/dbt/{args.project}",
        ]

        if args.select:
            run_args.extend(["--select", *args.select])

        if args.full_refresh:
            run_args.append("--full-refresh")

        subprocess.run(args=run_args)


if __name__ == "__main__":
    main()
