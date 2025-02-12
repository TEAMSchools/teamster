# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import subprocess


def main() -> None:
    commands = ["uv lock --upgrade", "uv sync"]

    for cmd in commands:
        subprocess.run(args=cmd.split())


if __name__ == "__main__":
    main()
