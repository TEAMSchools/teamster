# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import argparse
import pathlib
import subprocess


def datamodel_codegen(input_path: pathlib.Path):
    # trunk-ignore(bandit/B603)
    subprocess.run(
        args=[
            "datamodel-codegen",
            f"--input={input_path}",
            "--input-file-type=json",
            f"--output={input_path.parent}/{input_path.stem}.py",
            "--output-model-type=pydantic_v2.BaseModel",
            "--force-optional",
            "--use-standard-collections",
            "--use-union-operator",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("input_path", type=pathlib.Path)

    args = parser.parse_args()

    input_path: pathlib.Path = args.input_path

    if input_path.is_dir():
        for file in input_path.rglob("*.json"):
            datamodel_codegen(file)
    else:
        datamodel_codegen(input_path)


if __name__ == "__main__":
    main()
