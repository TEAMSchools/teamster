# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import os
import subprocess


def main() -> None:
    env = {**os.environ, "PATH": os.environ["PATH"] + ":/workspaces/teamster/.venv/bin"}

    commands = ["uv lock --upgrade", "uv sync", "trunk upgrade -y"]

    for cmd in commands:
        # trunk-ignore(bandit/B603)
        subprocess.run(args=cmd.split(), env=env)

    dbt_projects = [
        "amplify",
        "deanslist",
        "edplan",
        "finalsite",
        "iready",
        "overgrad",
        "pearson",
        "powerschool",
        "renlearn",
        "titan",
        "kippcamden",
        "kippmiami",
        "kippnewark",
        "kipppaterson",
        "kipptaf",
    ]

    for project in dbt_projects:
        # trunk-ignore(bandit/B603)
        subprocess.run(
            args=[*"dbt deps --upgrade".split(), f"--project-dir=src/dbt/{project}"],
            env=env,
        )


if __name__ == "__main__":
    main()
