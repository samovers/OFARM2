"""Profile-local fixture builders for SI binding engineering tests.

These helpers create small, fictional SI source snapshots for root-owned binding
tests. They do not define profile law, write conformance evidence, or move test
assertions out of the root suite.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager

from kernel import context
from kernel.context import ProductRegister, SIReferenceBindings
from kernel.profiles.si_ffs import ffsnaprave_adapter as ffsn
from kernel.profiles.si_ffs import gerk_adapter as gerk
from kernel.profiles.si_ffs import regsr_adapter as regsr
from kernel.profiles.si_ffs.ffsnaprave_adapter import FFSNapraveRegister
from kernel.profiles.si_ffs.gerk_adapter import GerkLayer
from kernel.store import Store


def uid():
    return uuid.uuid4().hex[:8]


@contextmanager
def selected_runtime(store):
    """Start bundle B after imports; never hot-switch the caller's runtime A."""
    runtime = Store(dsn=store.dsn)
    try:
        context.bootstrap(runtime)
        yield runtime
    finally:
        runtime.close()


def bundled_product_register(runtime):
    bindings = SIReferenceBindings.from_descriptor(
        runtime.runtime_bundle.descriptor,
        runtime_bundle=runtime.runtime_bundle,
    )
    register = ProductRegister(bindings, runtime_bundle=runtime.runtime_bundle)
    register.load_from_store(runtime)
    return register


def bundled_gerk_layer(runtime):
    layer = GerkLayer(runtime_bundle=runtime.runtime_bundle)
    layer.load_from_store(runtime)
    return layer


def bundled_ffsnaprave_register(runtime):
    register = FFSNapraveRegister(runtime_bundle=runtime.runtime_bundle)
    register.load_from_store(runtime)
    return register


def import_regsr_snapshot(store, register_day, decision):
    art = {
        "snapshotKind": "SI_UVHVVR_FFS_REG_HTML_PARSE",
        "parserCodeDigest": regsr.parser_code_digest(),
        "registerDay": register_day,
        "sourceUrl": regsr.REGSR_SOURCE_URL,
        "productCount": 1,
        "products": [
            {
                "regsrCode": "9001",
                "name": "FIKTIV (fictional)",
                "registrationValidUntil": "2028-08-15",
            }
        ],
        "productDetails": [
            {
                "name": "FIKTIV (fictional)",
                "decisions": [
                    {
                        "decisionType": "Registracija",
                        "decisionNumber": decision,
                        "issued": "2026-01-01",
                        "validUntil": "2028-08-15",
                    }
                ],
            }
        ],
        "rowProblems": [],
        "inputs": [{"file": "f.html", "digest": f"sha256:{uid()}cafe"}],
    }
    return regsr.import_regsr_snapshot(store, art)["snapshotRef"]


def import_gerk_snapshot(store, layer_date, pid):
    art = {
        "snapshotKind": "SI_MKGP_GERK_LAYER_PARSE",
        "parserCodeDigest": gerk.parser_code_digest(),
        "layerDate": layer_date,
        "canonicalVersionLabel": f"gerk-{layer_date}",
        "pidField": "GERK_PID",
        "attributesAvailable": ["GERK_PID", "RABA_ID", "AREA", "OPIS_RABE"],
        "featureCount": 1,
        "rowProblems": [],
        "features": [
            {
                "gerkPid": pid,
                "rabaId": "1300",
                "area": "0.5",
                "opisRabe": "trajni travnik (fictional)",
            }
        ],
        "inputs": [{"file": "f.csv", "digest": f"sha256:{uid()}cafe"}],
    }
    return gerk.import_gerk_snapshot(store, art)["snapshotRef"]


def import_ffsnaprave_snapshot(store, file_date, sticker, validity):
    art = {
        "snapshotKind": "SI_UVHVVR_FFS_NAPRAVE_PARSE",
        "fileDate": file_date,
        "canonicalVersionLabel": f"ffsn-{file_date}",
        "keyFieldsPresent": True,
        "attributesAvailable": list(ffsn.RETAINED_FIELDS),
        "inspectionCount": 1,
        "rowProblems": [],
        "inspections": [
            {
                "NapravaID": f"N{uid()[:5]}",
                "StevilkaZnaka": sticker,
                "VeljavnostZnaka": validity,
                "DatumPregleda": "2025-06-15",
                "SkladnostObPregledu": "DA",
            }
        ],
        "inputs": [{"file": "f.txt", "digest": f"sha256:{uid()}cafe"}],
    }
    return ffsn.import_ffsnaprave_snapshot(store, art)["snapshotRef"]
