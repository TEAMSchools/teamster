# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import subprocess


def main() -> None:
    commands = [
        "uv lock --upgrade",
        "uv export --output-file requirements.txt",
        "uv sync",
    ]

    for cmd in commands:
        # trunk-ignore(bandit/B603)
        subprocess.run(args=cmd.split(sep=" "))


if __name__ == "__main__":
    main()
