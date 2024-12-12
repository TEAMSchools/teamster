# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
import pathlib
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("input_file", type=pathlib.Path)

    args = parser.parse_args()

    input_file: pathlib.Path = args.input_file

    subprocess.run(
        args=[
            "/workspaces/teamster/.venv/bin/datamodel-codegen",
            f"--input={input_file}",
            "--input-file-type=json",
            f"--output={input_file.parent}/{input_file.stem}.py",
            "--output-model-type=pydantic_v2.BaseModel",
            "--force-optional",
            "--use-standard-collections",
            "--use-union-operator",
        ],
        shell=True,
    )


if __name__ == "__main__":
    main()
