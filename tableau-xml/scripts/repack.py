"""Repack an edited .twb into a .twbx, preserving the archive and the bytes.

A .twbx is a zip of the .twb plus the extracts and images. Rebuild it by copying
every entry from a donor archive and swapping only the .twb.

Two things this guards, both of which shipped broken in an earlier version:

* CRLF. Reading with `Path.read_text(encoding="utf-8")` applies universal
  newlines and the write then flattens 27,000+ CRLF endings to LF. The .twb on
  disk stayed correct while the one inside the .twbx did not, so nothing caught
  it. Read with `newline=""` and write bytes.
* Silent divergence. The packaged .twb is compared byte-for-byte against the
  source afterwards.

Usage:
    uv run python repack.py <edited.twb> <donor.twbx> <out.twbx>
"""

import sys
import zipfile
from pathlib import Path


def repack(twb: Path, donor: Path, out: Path) -> None:
    # newline="" keeps the file's own line endings; encode explicitly so no
    # translation can happen on the way back out.
    text = twb.read_text(encoding="utf-8", newline="")
    payload = text.encode("utf-8")

    with zipfile.ZipFile(donor) as z:
        entries = [(i, z.read(i.filename)) for i in z.infolist()]
    if not any(i.filename.endswith(".twb") for i, _ in entries):
        sys.exit(f"FAIL: donor {donor.name} contains no .twb")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z2:
        for info, data in entries:
            z2.writestr(info, payload if info.filename.endswith(".twb") else data)

    with zipfile.ZipFile(out) as z3:
        name = next(n for n in z3.namelist() if n.endswith(".twb"))
        packed = z3.read(name)
    if packed != payload:
        sys.exit("FAIL: packaged .twb differs from the source on disk")

    crlf = payload.count(b"\x0d\x0a")
    bare = payload.count(b"\x0a") - crlf
    print(f"  {out.name}: {out.stat().st_size / 1e6:.1f} MB")
    print(f"  packaged .twb byte-identical to source; CRLF {crlf}, bare LF {bare}")
    if bare:
        sys.exit("FAIL: bare LF present -- line endings were translated somewhere")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    repack(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
