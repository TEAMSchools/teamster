# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
import os
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "modules",
        nargs="*",
        default=["kipptaf", "kippcamden", "kippnewark", "kippmiami"],
    )

    args = parser.parse_args()

    module_args = []
    for m in args.modules:
        module_args.append(f"--module-name=teamster.code_locations.{m}.definitions")

    # trunk-ignore(bandit/B603)
    subprocess.run(
        args=[
            "dagster",
            "dev",
            "--code-server-log-level=debug",
            "--log-level=debug",
            *module_args,
        ],
        env={
            **os.environ,
            "PATH": os.environ["PATH"] + ":/workspaces/teamster/.venv/bin",
        },
    )


if __name__ == "__main__":
    main()
