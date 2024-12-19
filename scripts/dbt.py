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

    args = parser.parse_args()

    if args.command == "help":
        subprocess.run(args=["/workspaces/teamster/.venv/bin/dbt", "-h"])
    elif args.command == "sxs":
        run_args = [
            "/workspaces/teamster/.venv/bin/dbt",
            "run-operation",
            "stage_external_sources",
            f"--project-dir=src/dbt/{args.project}",
            "--vars=ext_full_refresh: true",
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

        subprocess.run(args=run_args)


if __name__ == "__main__":
    main()
