"""Run all draft checks; skipped verifier checks are an unsuccessful run."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
APP = HERE
OUTPUT = HERE / '.local' / 'test-evidence'
OUTPUT.mkdir(parents=True, exist_ok=True)
assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
assert os.environ['PYTHONDONTWRITEBYTECODE'] == '1'
for variable, folder in {
    'SPRAY_TEST_EVIDENCE': 'integration',
    'SPRAY_DETAILS_TEST_EVIDENCE': 'details',
    'SPRAY_VOLUME_TEST_EVIDENCE': 'volume',
    'SPRAY_JOB_TEST_EVIDENCE': 'job',
    'SPRAY_AMOUNT_RULE_TEST_EVIDENCE': 'amount-rules',
    'SPRAY_CONDITION_EVIDENCE_TEST_EVIDENCE': 'condition-evidence',
}.items():
    os.environ[variable] = str(OUTPUT / folder)
sys.path.insert(0, str(APP))
modules = ['test_draft', 'test_verifier', 'test_spray_details',
           'test_application_volume', 'test_job', 'test_example_amounts',
           'test_condition_evidence']
suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
result = unittest.TextTestRunner(verbosity=2).run(suite)
record = {'finishedAtUtc': datetime.now(timezone.utc).isoformat(),
          'modules': modules, 'testsRun': result.testsRun,
          'failures': [(str(test), detail) for test, detail in result.failures],
          'errors': [(str(test), detail) for test, detail in result.errors],
          'skipped': [(str(test), detail) for test, detail in result.skipped],
          'passedWithoutSkips': result.wasSuccessful() and not result.skipped,
          'scope': 'Local draft example with separately supplied verifier; no portability or real-use admission claim',
          'liveC4': 'NOT_EVALUATED', 'realApproval': 'BLOCKED', 'publication': 'BLOCKED'}
with (OUTPUT / 'python-results.json').open('w') as stream:
    json.dump(record, stream, indent=2); stream.write('\n')
raise SystemExit(0 if record['passedWithoutSkips'] else 1)
