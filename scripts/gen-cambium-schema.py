r"""Generate the Cambium NJGPA Pydantic model from a real summative record file.

The sample CSV is local-only (it contains student PII and is never committed).
The GENERATED file is the committed artifact. Re-run this only when Cambium
changes the file layout.

Usage:
    uv run --with python-slugify python scripts/gen-cambium-schema.py \
        "<path to a District_Summative_Record_File_GPA.csv>" \
        src/teamster/libraries/cambium/schema.py
"""

import csv
import sys
from pathlib import Path

from slugify import slugify

HEADER = """from pydantic import BaseModel


class SFTPFile(BaseModel):
    source_file_name: str | None = None


class NJGPA(SFTPFile):
"""


def main() -> None:
    sample_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    with open(file=sample_path, encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f))

    slugs = sorted({slugify(text=h, separator="_") for h in header})

    body = "".join(f"    {slug}: str | None = None\n" for slug in slugs)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(HEADER + body)

    print(f"wrote {out_path} with {len(slugs)} NJGPA fields")


if __name__ == "__main__":
    main()
