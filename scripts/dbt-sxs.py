# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
import json
import os
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("project")
    parser.add_argument("--select", "-s", nargs="*")
    parser.add_argument("--prod", action="store_true")
    parser.add_argument("--staging", action="store_true")
    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()

    cloud_storage_uri_base = (
        f"gs://teamster-{'test' if args.test else args.project}/dagster/{args.project}"
    )

    vars = {
        "ext_full_refresh": "true",
        "cloud_storage_uri_base": cloud_storage_uri_base,
    }

    run_args = [
        "dbt",
        "run-operation",
        "stage_external_sources",
        f"--project-dir=src/dbt/{args.project}",
        f"--vars={json.dumps(vars)}",
    ]

    if args.select:
        run_args.extend(["--args", " ".join(["select:", *args.select])])

    dbt_cloud_environment_type = "dev"
    if args.prod:
        dbt_cloud_environment_type = "prod"
    elif args.staging:
        dbt_cloud_environment_type = "staging"

    print(" ".join(run_args))

    # trunk-ignore(bandit/B603)
    subprocess.run(
        args=run_args,
        env={
            **os.environ,
            "DBT_CLOUD_ENVIRONMENT_TYPE": dbt_cloud_environment_type,
            "PATH": os.environ["PATH"] + ":/workspaces/teamster/.venv/bin",
        },
    )


if __name__ == "__main__":
    main()
