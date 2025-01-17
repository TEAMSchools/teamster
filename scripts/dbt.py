# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
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
