#!/usr/bin/env python3
"""REGSR snapshot parser (SI:UVHVVR-FFS-REG).

Parses locally saved HTML pages of the UVHVVR "Seznam registriranih FFS"
application (spletni2.furs.gov.si/FFS/REGSR/) into a structured snapshot
suitable for wrapping as an OFARM ReferenceSnapshot.

Zero dependencies. Input pages are windows-1250 encoded FrontPage-era HTML;
this parser is deliberately tolerant but fails loudly when the expected
table shape is missing, so silent format drift cannot produce empty
snapshots that look successful.

Usage:
  parse_regsr.py --list FFS_RegSezn.html [--detail FFS_Descr_*.html ...] \
                 [--source-url URL] -o snapshot.json

Honesty posture: the register page itself states the database is unofficial
and informational ("neuradna in zgolj informativnega značaja"); the legal
record is the registration decision. The snapshot therefore records the
lookup surface, the register-day stamp, and input digests so every
verification trace can disclose exactly what was read.
"""
from __future__ import annotations

import argparse
import hashlib
import html as htmllib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LIST_COLUMNS = ["Ime FFS", "Veljavnost", "Aktivna snov", "Proizvajalec", "Zastopnik"]


def read_cp1250(path: Path) -> str:
    return path.read_bytes().decode("cp1250", errors="replace")


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = htmllib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_si_date(raw: str) -> str | None:
    match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", raw)
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_register_day(page_text: str) -> str | None:
    match = re.search(r"na dan\s+(\d{1,2}\.\d{1,2}\.\d{4})", page_text)
    return parse_si_date(match.group(1)) if match else None


def parse_list(path: Path) -> dict:
    page = read_cp1250(path)
    rows = re.findall(r"<tr.*?</tr>", page, re.I | re.S)
    if len(rows) < 2:
        raise SystemExit(f"FORMAT DRIFT: no table rows found in {path}")
    header_cells = [strip_tags(c) for c in re.findall(r"<td.*?</td>", rows[0], re.I | re.S)]
    if not header_cells or "Ime FFS" not in header_cells[0]:
        raise SystemExit(f"FORMAT DRIFT: unexpected header {header_cells!r} in {path}")

    products, problems = [], []
    for row in rows[1:]:
        cells = re.findall(r"<td.*?</td>", row, re.I | re.S)
        if len(cells) < 5:
            problems.append({"row": strip_tags(row)[:120], "problem": "fewer than 5 cells"})
            continue
        link = re.search(r'href="[^"]*FFS_Descr\.asp\?[^"]*CODE=(\d+)"', cells[0], re.I)
        name = strip_tags(cells[0])
        valid_until = parse_si_date(strip_tags(cells[1]))
        if not name:
            problems.append({"row": strip_tags(row)[:120], "problem": "empty product name"})
            continue
        products.append({
            "regsrCode": link.group(1) if link else None,
            "name": name,
            "registrationValidUntil": valid_until,
            "activeSubstancesRaw": strip_tags(cells[2]),
            "manufacturer": strip_tags(cells[3]),
            "representative": strip_tags(cells[4]),
        })
    if not products:
        raise SystemExit(f"FORMAT DRIFT: zero products parsed from {path}")
    return {
        "registerDay": parse_register_day(page),
        "products": products,
        "rowProblems": problems,
        "inputDigest": sha256(path),
        "inputFile": path.name,
    }


def parse_detail(path: Path) -> dict:
    page = read_cp1250(path)
    text = strip_tags(page)

    def field(label: str) -> str | None:
        match = re.search(re.escape(label) + r":\s*(.*?)(?=\s+[A-ZČŠŽ][\w čšžćđ()/,-]*?:|$)", text)
        return match.group(1).strip(" ;") or None if match else None

    substances = []
    sub_block = re.search(r"Aktivna snov\s+Delež \(%\)\s+Carinska skupina\s+CAS\s+MoA\s+(.*?)(?:Formulacija:)", text)
    if sub_block:
        pattern = re.compile(r"([a-zčšž][\w \-.]*?)\s+([\d.,]+)\s+(\d{6,10})\s+([\d-]+)\s+((?:IRAC|FRAC|HRAC)[^;]*?(?=\s+[a-zčšž][\w \-.]*?\s+[\d.,]+\s+\d{6,10}|$))")
        for m in pattern.finditer(sub_block.group(1)):
            substances.append({"name": m.group(1).strip(), "sharePct": m.group(2),
                               "customsGroup": m.group(3), "cas": m.group(4), "moa": m.group(5).strip()})

    def eppo_pairs(label: str) -> list[dict]:
        block = re.search(re.escape(label) + r":\s*(.*?)(?=Opozorila|Uporaba proti:|Uporabe in koncentracije|$)", text)
        if not block:
            return []
        return [{"eppoCode": code, "label": lbl.strip()}
                for code, lbl in re.findall(r"([0-9A-Z]{4,8})\s*:\s*([^;()]+(?:\([^)]*\))?)", block.group(1))]

    decisions = []
    for m in re.finditer(r"(Registracija|Dovoljenje[\w ]*?|Vzporedno[\w ]*?)\s+([A-Z]?\d{4,6}-\d+/\d+(?:/\d+)*)\s+(\d{1,2}\.\d{1,2}\.\d{4})\s+(\d{1,2}\.\d{1,2}\.\d{4})", text):
        decisions.append({"decisionType": m.group(1).strip(), "decisionNumber": m.group(2),
                          "issued": parse_si_date(m.group(3)), "validUntil": parse_si_date(m.group(4))})

    return {
        "registerDay": parse_register_day(text),
        "name": field("Ime sredstva"),
        "saleChannel": field("Mesto prodaje"),
        "activeSubstances": substances,
        "formulation": field("Formulacija"),
        "hazardGroup": field("Skupina nevarnosti"),
        "signalWord": field("Opozorilna beseda"),
        "useCategory": field("Uporaba"),
        "manufacturer": field("Proizvajalec"),
        "authorizedCrops": eppo_pairs("Uporaba na"),
        "targetOrganisms": eppo_pairs("Uporaba proti"),
        "decisions": decisions,
        "inputDigest": sha256(path),
        "inputFile": path.name,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True, type=Path)
    ap.add_argument("--detail", nargs="*", type=Path, default=[])
    ap.add_argument("--source-url", default="https://spletni2.furs.gov.si/FFS/REGSR/FFS_RegSezn.asp?top=1")
    ap.add_argument("-o", "--out", required=True, type=Path)
    args = ap.parse_args()

    listing = parse_list(args.list)
    details = [parse_detail(p) for p in args.detail]
    snapshot = {
        "snapshotKind": "SI_UVHVVR_FFS_REG_HTML_PARSE",
        "officialStatusNote": "Register web database self-declares as unofficial/informational; legal record is the registration decision (odlocba). Lookup surface disclosed per profile posture.",
        "capturedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "registerDay": listing["registerDay"] or (details[0]["registerDay"] if details else None),
        "sourceUrl": args.source_url,
        "productCount": len(listing["products"]),
        "products": listing["products"],
        "productDetails": details,
        "rowProblems": listing["rowProblems"],
        "inputs": [{"file": listing["inputFile"], "digest": listing["inputDigest"]}]
                  + [{"file": d["inputFile"], "digest": d["inputDigest"]} for d in details],
    }
    args.out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"products={snapshot['productCount']} details={len(details)} "
          f"registerDay={snapshot['registerDay']} problems={len(listing['rowProblems'])} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
