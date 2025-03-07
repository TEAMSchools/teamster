# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
import os
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("project")
    parser.add_argument("--select", "-s", nargs="*")
    parser.add_argument("--dev", action="store_true")

    args = parser.parse_args()

    cloud_storage_uri_base = (
        f"gs://teamster-{'test' if args.dev else args.project}/dagster/{args.project}"
    )

    run_args = [
        "dbt",
        "run-operation",
        "stage_external_sources",
        f"--project-dir=src/dbt/{args.project}",
        f"--vars={{'ext_full_refresh': 'true', 'cloud_storage_uri_base': '{cloud_storage_uri_base}'}}",
    ]

    if args.select:
        run_args.extend(["--args", " ".join(["select:", *args.select])])

    # trunk-ignore(bandit/B603)
    subprocess.run(
        args=run_args,
        env={
            **os.environ,
            "DBT_CLOUD_ENVIRONMENT_TYPE": "dev" if args.dev else "prod",
            "PATH": os.environ["PATH"] + ":/workspaces/teamster/.venv/bin",
        },
    )


if __name__ == "__main__":
    main()
