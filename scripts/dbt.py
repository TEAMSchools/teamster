# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
import json
import pathlib
import re
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("command")
    parser.add_argument("project")
    parser.add_argument("--select", nargs="*")
    parser.add_argument("--prod", action="store_true")

    args = parser.parse_args()

    dbt_path = "/workspaces/teamster/.venv/bin/dbt"

    if args.command == "sxs":
        cloud_storage_uri_base = (
            "gs://teamster-"
            + (args.project if args.prod else "test")
            + f"{args.project}/dagster/{args.project}"
        )

        run_args = [
            dbt_path,
            "run-operation",
            "stage_external_sources",
            f"--project-dir=src/dbt/{args.project}",
            f"--vars={{'ext_full_refresh': 'true', 'cloud_storage_uri_base': '{cloud_storage_uri_base}'}}",
        ]

        if args.select:
            run_args.extend(["--args", " ".join(["select:", *args.select])])

        subprocess.run(args=run_args)
    elif args.command == "yaml":
        project_dir = pathlib.Path(f"src/dbt/{args.project}")

        list_args = [
            dbt_path,
            "list",
            f"--project-dir={project_dir}",
            "--resource-type=model",
            "--output=name",
        ]

        if args.select:
            list_args.extend(["--select", " ".join(*args.select)])

        print(" ".join(list_args))
        model_names = [
            o.decode()
            for o in subprocess.check_output(args=list_args).split(b"\n")
            if re.match(pattern=r"(\w+)", string=o.decode())
        ]

        for model_name in model_names:
            run_args = [
                dbt_path,
                "run-operation",
                "generate_model_yaml",
                f"--project-dir={project_dir}",
                "--args",
                json.dumps({"model_names": [model_name]}),
            ]

            print(" ".join(run_args))
            yaml = subprocess.check_output(args=run_args).decode()

            yaml = "\n".join(
                [
                    line
                    for line in yaml.splitlines()[3:]
                    if line.strip() not in ["", 'description: ""']
                ]
            )

            file_parent = project_dir / "models/properties"

            file_parent.mkdir(parents=True, exist_ok=True)
            with open(file=f"{file_parent}/{model_name}.yml", mode="w") as f:
                f.write(yaml)


if __name__ == "__main__":
    main()
