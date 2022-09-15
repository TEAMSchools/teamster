import argparse
import gzip
import json
import pathlib
import statistics


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(usage="%(prog)s [FILE]...")
    parser.add_argument("file")
    return parser


def main():
    parser = init_argparse()
    args = parser.parse_args()

    if args.file:
        file_path = pathlib.Path(args.file).absolute()

        with gzip.open(file_path, "rb") as gz:
            debug_data = json.load(gz)

        event_list = [dd for dd in debug_data["event_list"] if dd.get("dagster_event")]
        step_success = [
            e
            for e in event_list
            if e["dagster_event"]["event_type_value"] == "STEP_SUCCESS"
        ]
        step_ms = [
            ss["dagster_event"]["event_specific_data"]["duration_ms"]
            for ss in step_success
        ]

        n_steps = len(step_success)
        total_ms = sum(step_ms)
        avg_ms = statistics.fmean(step_ms)
        print(
            f"{args.file}\n",
            f"# Steps:\t{n_steps}\n",
            f"Total Ms:\t{total_ms}\n",
            f"Avg Ms:\t{avg_ms}",
        )


if __name__ == "__main__":
    main()
