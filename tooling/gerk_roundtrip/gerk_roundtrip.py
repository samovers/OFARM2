#!/usr/bin/env python3
"""GERK open-data round-trip check (M0 item 7).

Proves that a known farm's GERK-PIDs resolve against the national open-data
GERK layer (OPSI / MKGP public viewer download), so onboarding can fill
parcel geometry/areas from open data with no per-farmer government export.

Privacy: run locally. Pass real GERK-PIDs on the command line or in a file;
they are never written anywhere — the report contains counts, booleans, and
format documentation only. Paste the report output; keep the inputs.

Zero dependencies: reads the .dbf attribute table of the shapefile directly
(streaming, constant memory), or a .csv export. Geometry is not read — the
round-trip checks existence and attributes; geometry usability is implied by
the layer being a shapefile.

Usage:
  python3 gerk_roundtrip.py --dbf GERK.dbf --pids 1234567,2345678
  python3 gerk_roundtrip.py --csv gerk.csv --pids-file my_pids.txt
"""
from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path

PID_FIELD_CANDIDATES = ["GERK_PID", "GERKPID", "GERK_PID_", "PID", "ID_GERK"]
INTERESTING = ["RABA_ID", "VRSTA_RABE", "RABA", "POVRSINA", "POV_HA", "AREA",
               "NUP", "GRPOV", "BLOK_ID", "DOM_IME", "DOMACE_IME", "D_OD"]


def read_dbf_header(fh):
    header = fh.read(32)
    if len(header) < 32:
        raise SystemExit("not a DBF file (short header)")
    record_count = struct.unpack("<I", header[4:8])[0]
    header_size, record_size = struct.unpack("<HH", header[8:12])
    fields = []
    while True:
        descriptor = fh.read(32)
        if not descriptor or descriptor[0] == 0x0D:
            break
        name = descriptor[:11].split(b"\x00")[0].decode("ascii", errors="replace")
        ftype = chr(descriptor[11])
        length = descriptor[16]
        fields.append((name, ftype, length))
    fh.seek(header_size)
    return record_count, record_size, fields


def iter_dbf(path: Path):
    with open(path, "rb") as fh:
        record_count, record_size, fields = read_dbf_header(fh)
        yield [f[0] for f in fields]
        for _ in range(record_count):
            raw = fh.read(record_size)
            if len(raw) < record_size:
                break
            if raw[0:1] == b"*":  # deleted record
                continue
            offset, row = 1, []
            for _, _, length in fields:
                row.append(raw[offset:offset + length].decode("cp1250", errors="replace").strip())
                offset += length
            yield row


def iter_csv(path: Path):
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        sample = fh.read(4096); fh.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        for row in csv.reader(fh, delimiter=delim):
            yield row


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dbf", type=Path)
    src.add_argument("--csv", type=Path)
    ap.add_argument("--pids", help="comma-separated GERK-PIDs")
    ap.add_argument("--pids-file", type=Path, help="file with one GERK-PID per line")
    ap.add_argument("--pid-field", help="attribute name if auto-detect fails")
    args = ap.parse_args()

    pids: set[str] = set()
    if args.pids:
        pids |= {p.strip() for p in args.pids.split(",") if p.strip()}
    if args.pids_file:
        pids |= {line.strip() for line in args.pids_file.read_text().splitlines() if line.strip()}
    if not pids:
        raise SystemExit("no GERK-PIDs given (--pids or --pids-file)")

    rows = iter_dbf(args.dbf) if args.dbf else iter_csv(args.csv)
    header = next(rows)
    pid_field = args.pid_field or next((c for c in PID_FIELD_CANDIDATES if c in header), None)
    if not pid_field:
        print("REPORT: pid-field auto-detect FAILED.")
        print(f"REPORT: available attributes: {header}")
        print("Re-run with --pid-field <name>. This output is safe to paste.")
        return 1
    pid_index = header.index(pid_field)
    kept = [h for h in header if h.upper() in INTERESTING]

    found, scanned = {}, 0
    for row in rows:
        scanned += 1
        value = row[pid_index].split(".")[0].strip()
        if value in pids:
            found[value] = {h: row[header.index(h)] for h in kept}
        if len(found) == len(pids):
            break

    print("=== GERK ROUND-TRIP REPORT (safe to paste: no real values included) ===")
    print(f"layer records scanned: {scanned}")
    print(f"pid attribute used:    {pid_field}")
    print(f"attributes available:  {header}")
    print(f"pids requested:        {len(pids)}")
    print(f"pids found:            {len(found)}")
    print(f"pids missing:          {len(pids) - len(found)}")
    for pid, attrs in found.items():
        masked = "…" + pid[-2:]
        summary = {k: ("present" if v else "empty") for k, v in attrs.items()}
        print(f"  parcel {masked}: attributes {summary}")
    print("VERDICT:", "PASS — onboarding can resolve parcels from the open layer"
          if len(found) == len(pids) else
          "PARTIAL/FAIL — investigate missing pids (layer vintage vs izpis date?)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
