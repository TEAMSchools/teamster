# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
import json
import os
import pathlib
import re
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("project")
    parser.add_argument("--select", "-s", nargs="*")
    parser.add_argument("--dev", action="store_true")

    args = parser.parse_args()

    project_dir = pathlib.Path(f"src/dbt/{args.project}")
    env = {
        **os.environ,
        "PATH": os.environ["PATH"] + ":/workspaces/teamster/.venv/bin",
        "DBT_CLOUD_ENVIRONMENT_TYPE": "dev" if args.dev else "prod",
    }

    if len(args.select) == 1:
        model_names = args.select
    else:
        list_args = [
            "dbt",
            "list",
            f"--project-dir={project_dir}",
            "--resource-type=model",
            "--output=name",
        ]

        if args.select:
            list_args.extend(["--select", " ".join(*args.select)])

        print(" ".join(list_args))

        # trunk-ignore(bandit/B603)
        output = subprocess.check_output(args=list_args, env=env)

        model_names = [
            o.decode()
            for o in output.split(b"\n")
            if re.match(pattern=r"(\w+)", string=o.decode())
        ]

    for model_name in model_names:
        file_path = project_dir / f"models/properties/{model_name}.yml"

        # skip if file has already been created
        # if file_path.exists():
        #     continue

        run_args = [
            "dbt",
            "run-operation",
            "generate_model_yaml",
            f"--project-dir={project_dir}",
            "--args",
            json.dumps({"model_names": [model_name]}),
        ]

        print(" ".join(run_args))
        # trunk-ignore(bandit/B603)
        yaml = subprocess.check_output(args=run_args, env=env).decode()

        yaml = "\n".join(
            [
                line
                for line in yaml.splitlines()[3:]
                if line.strip() not in ["", 'description: ""']
            ]
        )

        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file=file_path, mode="w") as io_wrapper:
            io_wrapper.write(yaml)


if __name__ == "__main__":
    main()
