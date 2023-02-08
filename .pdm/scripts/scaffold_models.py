import argparse
import pathlib

from yaml import safe_load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sources_file_path", type=pathlib.Path)
    args = parser.parse_args()

    with args.sources_file_path.open(mode="r") as f:
        sources = safe_load(f)

    tables = sources["sources"][0]["tables"]

    for t in tables:
        model_path: pathlib.Path = args.sources_file_path.parent / (
            t["name"].replace("src_", "") + ".sql"
        )
        print(model_path)
        model_path.touch(exist_ok=True)


if __name__ == "__main__":
    main()
