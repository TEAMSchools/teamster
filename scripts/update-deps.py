# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import subprocess


def main() -> None:
    commands = ["uv lock --upgrade", "uv sync", "trunk upgrade -y"]

    for cmd in commands:
        # trunk-ignore(bandit/B603)
        subprocess.run(args=cmd.split())


if __name__ == "__main__":
    main()
