"""Locate the already selected verifier; never create or relax its environment."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

SELECTION_SHA256 = 'aa28df23b8e1972e1a167abb3bcfa3e1132585a0fc7b21bf85c63d44ef75d23a'
location = os.environ.get('SPRAY_DRAFT_VERIFIER')
if not location or not Path(location).is_absolute():
    raise RuntimeError('Set SPRAY_DRAFT_VERIFIER to the absolute directory of the separately supplied, selected verifier. See README.md. No substitute verifier is available.')
VERIFIER_ROOT = Path(location).resolve(strict=True)
selection_bytes = (VERIFIER_ROOT / 'dependency-selection.json').read_bytes()
if hashlib.sha256(selection_bytes).hexdigest() != SELECTION_SHA256:
    raise RuntimeError('The supplied verifier has a different execution selection. A separate reviewed setup and consumer re-pin are required.')
pin = json.loads((Path(__file__).resolve().parent / 'verifier-selection.json').read_bytes())
transport_path = VERIFIER_ROOT / 'owner_calls.py'
if hashlib.sha256(transport_path.read_bytes()).hexdigest() != pin['ownerTransportSha256']:
    raise RuntimeError('The supplied verifier transport has changed.')
spec = importlib.util.spec_from_file_location('spray_draft_verifier_transport', transport_path)
TRANSPORT = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = TRANSPORT
spec.loader.exec_module(TRANSPORT)
TRANSPORT.candidate_closure(pin['manifestRawSha256'])
# The separate execution boundary owns path resolution and dependency policy.
EXECUTION_SELECTION = TRANSPORT.load_selection()
SOURCE_ROOTS = {
    'repository': Path(__file__).resolve().parents[3],
    'verifier': VERIFIER_ROOT,
    'environment': Path(EXECUTION_SELECTION['libraries']['manifestPath']).parent,
}
