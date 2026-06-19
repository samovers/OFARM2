"""SI REGSR adapter (M2 P1) — package content for the UVHVVR "Seznam
registriranih FFS" product-authorisation register (`SI:UVHVVR-FFS-REG`, D9).

This wires the REGSR scheme to the GENERIC mechanisms: it parses the official
HTML surface (reusing tooling/regsr_snapshot/parse_regsr.py as a library — never
forked), imports the parse as a dated REGSR `ReferenceSnapshot` through the
generic G2 `ImportRunner`, and exposes a REGSR lookup that drives the generic G3
`ReferenceResolver` at identity grade. ALL REGSR specifics (scheme name, lookup
surface, the decision-number-as-identity rule, the weekly cadence) live HERE;
kernel/adapters.py and kernel/verification.py stay scheme-agnostic.

Claim limits: snapshot-based, no live registry integration — the register
declares itself unofficial/informational, the legal record is the *odločba*
(D9; UNSUPPORTED_SURFACES.md). This adapter records the lookup surface and
input digests so every verification trace discloses exactly what was read; it
makes no current-compliance or production-currentness claim.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from ... import config
from ...adapters import ImportRunner, ParseResult
from ...context import REGSR_DATA_FAMILY, REGSR_SNAPSHOT_PREFIX, now_iso
from ...contracts import sha256_of
from ...verification import IDENTITY, NONE, LookupResult, ReferenceResolver

# REGSR scheme constants (SI-specific — D9). Identity = Številka odločbe
# (registration decision number) + validity dates; trade name is evidence, page
# record numbers are locators, never identity.
REGSR_AUTHORITY_REF = "party:si.uvhvvr"
REGSR_JURISDICTION_REF = "jurisdiction:SI"
REGSR_PROFILE_REF = config.CODE_BINDING_PROFILE_REF
REGSR_SCHEME = "SI:UVHVVR-FFS-REG"
REGSR_KEY_FIELD = "stevilka-odlocbe"          # the decision number (identity key, D9)
REGSR_DOMAIN = ("SI crop-protection product authorisation register "
                "(UVHVVR Seznam registriranih FFS)")
REGSR_SOURCE_URL = "https://spletni2.furs.gov.si/FFS/REGSR/FFS_RegSezn.asp?top=1"
REGSR_SOURCE_SURFACE = "surface:spletni2.furs.gov.si.FFS.REGSR"
REGSR_PARSER_REF = "tooling/regsr_snapshot/parse_regsr.py"
# the trace lookup-surface enum has no SI-specific value; the precise surface is
# recorded on the imported snapshot's sourceArtifactRefs and in the trace's
# queryInputs/snapshotRefs (the trace's own lookupSurface stays OTHER)
REGSR_LOOKUP_SURFACE = "OTHER"

# D9 / PROFILE.md: weekly scripted parse of the official HTML pages -> dated
# ReferenceSnapshot, with a monthly manual floor. Declared, not scheduled here
# (cron wiring is out of scope — an injectable trigger calls run-import).
REGSR_CADENCE = {
    "period": "WEEKLY",
    "manualFloor": "MONTHLY",
    "posture": "unofficial-surface-over-official-content (D9, ERRATA E-002)",
    "liveIntegration": False,
}


def _parser():
    """Load tooling/regsr_snapshot/parse_regsr.py as a library (reuse, no fork)."""
    path = config.PACKAGE_ROOT / "tooling" / "regsr_snapshot" / "parse_regsr.py"
    spec = importlib.util.spec_from_file_location("ofarm_regsr_parser", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_regsr_html(list_path, detail_paths=()) -> dict:
    """Parse saved REGSR HTML (list + optional detail pages) into a register
    artifact, reusing the tooling parser. No live HTTP. Returns the artifact
    (products, productDetails, registerDay, input digests) the importer wraps."""
    pr = _parser()
    listing = pr.parse_list(Path(list_path))
    details = [pr.parse_detail(Path(p)) for p in detail_paths]
    register_day = listing["registerDay"] or (details[0]["registerDay"] if details else None)
    inputs = ([{"file": listing["inputFile"], "digest": listing["inputDigest"]}]
              + [{"file": d["inputFile"], "digest": d["inputDigest"]} for d in details])
    return {
        "snapshotKind": "SI_UVHVVR_FFS_REG_HTML_PARSE",
        "registerDay": register_day,
        "sourceUrl": REGSR_SOURCE_URL,
        "productCount": len(listing["products"]),
        "products": listing["products"],
        "productDetails": details,
        "rowProblems": listing["rowProblems"],
        "inputs": inputs,
    }


def import_regsr_snapshot(store, artifact, *, register_day=None,
                          source_artifact_ref=None) -> dict:
    """Import a parsed REGSR artifact as a dated REGSR `ReferenceSnapshot` via the
    generic G2 ImportRunner. The effective date is the register day; the source
    digest and surface ride the snapshot's sourceArtifactRefs. A malformed/partial
    parse is refused by the generic runner (no snapshot)."""
    register_day = register_day or artifact.get("registerDay")
    if not register_day:
        # A parse with no datable register day is a source-fidelity loss. Route
        # it through the GENERIC governed refusal path (ImportRunner) rather than
        # hand-building a mini problem that bypasses the audit trail (PR #12
        # review): this yields a real RuntimeProblem AND a GOVERNED_IMPORT/REFUSED
        # gate-log entry, with no snapshot and no data row. There is no snapshot
        # id to reference (the register day is what dates it), so the refusal
        # carries no related ref — honest, not a fabricated sid.
        result = ImportRunner(store).run_import(
            ParseResult(ok=False, error="REGSR parse carries no register day; "
                        "cannot date a snapshot"),
            {"referenceSnapshotId": None}, data_family=REGSR_DATA_FAMILY)
        return {**result, "disposition": "NO_REGISTER_DAY", "registerDay": None}
    sid = f"{REGSR_SNAPSHOT_PREFIX}.{register_day}"
    # The import basis digests the WHOLE parsed artifact — list AND detail pages,
    # parsed products and decisions — not just inputs[0] (the list page). Detail
    # pages carry the decision-number identity evidence (D9), so a detail change
    # under an unchanged list digest changes this digest, hence the snapshot
    # payload: a conflicting re-import is then REFUSED, never a silent
    # ALREADY_IMPORTED replay that leaves stale identity data (PR #12 hostile B1).
    digest = sha256_of(artifact)
    meta = {
        "referenceSnapshotId": sid,
        "referenceClass": "CODE_LIST",
        "domain": REGSR_DOMAIN,
        "issuingAuthorityRef": REGSR_AUTHORITY_REF,
        "jurisdictionRef": REGSR_JURISDICTION_REF,
        "canonicalVersionLabel": f"register-day-{register_day}.parse-{now_iso()[:10]}",
        "effectiveFrom": f"{register_day}T00:00:00Z",
        "sourceArtifactRefs": [REGSR_SOURCE_SURFACE],
        "notes": "REGSR HTML parse; register self-declares unofficial/informational, "
                 "legal record is the odlocba (D9). Parser: " + REGSR_PARSER_REF,
    }
    result = ImportRunner(store).run_import(
        ParseResult(ok=True, sourceDigest=digest, artifactRef=source_artifact_ref,
                    recordCount=len(artifact.get("products", [])), records=artifact),
        meta, data_family=REGSR_DATA_FAMILY)
    return {**result, "registerDay": register_day}


def regsr_lookup(product_register, *, issued=None, valid_until=None):
    """A G3 lookup callable bound to a REGSR `ProductRegister`, grading identity
    by the D9 composite key — decision number (Številka odločbe) PLUS validity
    dates (issued / validUntil), never the decision number alone (PR #12 hostile
    B2). Per decision number:

      * 0 matches             -> NONE / NOT_FOUND        (resolver -> review)
      * 1 distinct identity   -> IDENTITY / AUTHORISED   (resolver -> CONFIRM)
      * >1 differing validity -> NONE / MULTIPLE_CANDIDATES + discrepancy
                                 (resolver -> review; never collapse one / PASS)

    When `issued`/`valid_until` are supplied the candidates are first filtered to
    that composite, so a caller who knows the full key disambiguates a number
    that would otherwise be ambiguous. regsrCode stays a locator, never identity.
    Returns a closure of the G3 `lookup(snapshot_id, query_value)` shape."""
    def lookup(snapshot_id, decision_number) -> LookupResult:
        ids = product_register.identities_by_decision(snapshot_id, decision_number)
        if issued or valid_until:
            ids = [c for c in ids
                   if (not issued or c.get("decision", {}).get("issued") == issued)
                   and (not valid_until or c.get("decision", {}).get("validUntil") == valid_until)]
        if not ids:
            return LookupResult(grade=NONE, candidate_count=0, status_observed="NOT_FOUND")
        if len(ids) > 1:
            # D9 composite key is ambiguous on the decision number alone -> route
            # to review with the ambiguity recorded; never collapse to one / PASS.
            return LookupResult(
                grade=NONE, candidate_count=len(ids),
                status_observed="MULTIPLE_CANDIDATES",
                discrepancies=[{"discrepancyType": "OTHER", "severity": "REVIEW_REQUIRED",
                                "note": f"decision number {decision_number} matched "
                                        f"{len(ids)} records with differing validity "
                                        "dates; D9 identity is the composite key (number + "
                                        "validity), so this is ambiguous, not identity — "
                                        "supply issued/validUntil to disambiguate"}])
        confirmed = ids[0]
        decision = confirmed.get("decision", {})
        dates = {}
        if decision.get("issued"):
            dates["statusEffectiveFrom"] = f"{decision['issued']}T00:00:00Z"
        valid_u = decision.get("validUntil") or confirmed.get("registrationValidUntil")
        if valid_u:
            dates["statusEffectiveUntil"] = f"{valid_u}T00:00:00Z"
        return LookupResult(grade=IDENTITY, candidate_count=1,
                            external_id=decision_number, status_observed="AUTHORISED",
                            dates_observed=dates or None)
    return lookup


def verify_product_authorisation(store, cur, product_register, decision_number, *,
                                 issued=None, valid_until=None,
                                 as_of=None, created_by=None) -> dict:
    """Verify a product's authorisation identity by its REGSR decision number
    through the generic G3 resolver, recording an ExternalRegistryVerificationTrace.
    Identity-grade only where the D9 composite key (decision number + validity)
    resolves unambiguously; an ambiguous or absent key routes to review
    (PRODUCT_BINDING_UNRESOLVED) — free text never becomes identity (D9). Pass
    `issued`/`valid_until` to disambiguate an otherwise-ambiguous decision number."""
    return ReferenceResolver(store).verify(
        cur, query_value=decision_number, snapshot_prefix=REGSR_SNAPSHOT_PREFIX,
        lookup=regsr_lookup(product_register, issued=issued, valid_until=valid_until),
        profile_ref=REGSR_PROFILE_REF, authority_ref=REGSR_AUTHORITY_REF,
        jurisdiction_ref=REGSR_JURISDICTION_REF, scheme=REGSR_SCHEME,
        key_field=REGSR_KEY_FIELD, purpose="PRODUCT_AUTHORISATION_IDENTITY",
        lookup_surface=REGSR_LOOKUP_SURFACE, external_id_role="AUTHORISATION_NUMBER",
        review_reason_code="PRODUCT_BINDING_UNRESOLVED", as_of=as_of, created_by=created_by)
