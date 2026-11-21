"""Focused tests of the draft journey; no live source or domain acceptance."""
import copy
import json
import sqlite3
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import DraftInbox, Problem, make_server
from draft import HERE, GATES, check_capture, sha


def example():
    return {'format': 'spray-draft.v1', 'draftId': str(uuid.uuid4()),
            'capturedAt': '2026-11-12T11:00:00Z', 'catalogSha256': sha((HERE / 'catalog.json').read_bytes()),
            'productId': 'binding:demo-product-a', 'parcelId': 'field:demo-orchard', 'cropId': 'binding:demo-apples',
            'dose': {'value': '0.30', 'unitId': 'litres-per-hectare'},
            'event': {'start': '2026-11-11T09:00:00Z', 'end': '2026-11-11T09:45:00Z',
                      'startLocal': '2026-11-11T10:00', 'endLocal': '2026-11-11T10:45', 'timeZone': 'Europe/Ljubljana'}}


def raw(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode()


class DraftOnlyVerifier:
    """Old capture/storage unit tests do not count as actual verifier runs."""
    def check(self, _draft, _directory):
        return {'state': 'NOT_RUN', 'message': 'Capture/storage unit-test double; verifier covered separately.',
                'completeClaim': False, 'liveC4': 'NOT_EVALUATED', 'publication': 'BLOCKED', 'findings': []}


class DraftJourneyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.inbox = DraftInbox(Path(self.directory.name) / 'drafts.sqlite3', verifier=DraftOnlyVerifier())

    def tearDown(self):
        self.directory.cleanup()

    def checked(self, capture):
        return check_capture(raw(capture), (HERE / 'catalog.json').read_bytes(), '2026-11-12T12:00:00Z')

    def assert_gated(self, result):
        self.assertEqual(result['gates'], GATES)
        self.assertIsNone(result['typedClaim'])
        self.assertEqual(result['c3Completion'], 'NOT_CLAIMED')

    def test_entry_sync_review_preserves_source_and_distinct_times(self):
        capture = example()
        original = raw(capture)
        saved = self.inbox.save(original)
        self.assertTrue(saved['canAcknowledgeDraft'], saved['issues'])
        self.assertEqual(saved['originalText'].encode(), original)
        source = saved['draftSource']
        self.assertEqual(source['capturedAt'], capture['capturedAt'])
        self.assertEqual(source['effectiveTimeInterval']['start'], capture['event']['start'])
        self.assertNotEqual(saved['receivedAt'], source['capturedAt'])
        self.assertEqual(source['actualQuantityParameters'][0]['reportedValue'], '0.30')
        self.assertEqual(source['actualQuantityParameters'][0]['value'], 0.3)
        self.assertEqual(source['actualQuantityParameters'][0]['parameterRole'], 'DOSE')
        self.assertEqual(source['sourcePayload']['sourcePayloadHash'], 'sha256:' + sha(original))
        evidence = saved['draftEvidence']
        self.assertEqual(source['evidenceRefs'], [evidence['evidenceRecordId']])
        self.assertEqual(evidence['rawAssetDigest'], 'sha256:' + sha(original))
        self.assertEqual(evidence['rawAssetRef'], 'draft-capture:' + capture['draftId'])
        self.assertEqual(evidence['evidenceClass'], 'OTHER')  # The user's report, no invented photo.
        self.assertEqual(evidence['interpretation'], {'interpretationClass': 'NONE'})
        self.assertEqual(source['recordState'], 'CLAIMED')
        reviewed = self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': sha(original)}))
        self.assertIsNotNone(reviewed['reviewedAt'])
        self.assert_gated(reviewed)
        self.assertEqual(reviewed['originalText'], saved['originalText'])

    def test_retry_is_idempotent_and_conflicting_original_is_not_overwritten(self):
        capture = example(); original = raw(capture)
        first = self.inbox.save(original)
        self.assertEqual(self.inbox.save(original), first)
        with self.assertRaises(Problem) as raised:
            self.inbox.save(original + b' ')
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(self.inbox.read(capture['draftId'])['originalText'].encode(), original)
        with self.inbox.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM captures').fetchone()[0], 1)

    def test_review_requires_exact_saved_copy_and_retries_do_not_create_decisions(self):
        capture = example(); saved = self.inbox.save(raw(capture))
        with self.assertRaises(Problem):
            self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': '0' * 64}))
        body = raw({'originalSha256': saved['originalSha256']})
        first = self.inbox.acknowledge(capture['draftId'], body)
        self.assertEqual(self.inbox.acknowledge(capture['draftId'], body), first)
        with self.inbox.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM acknowledgements').fetchone()[0], 1)
            self.assertEqual({r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}, {'captures', 'acknowledgements'})

    def test_unknown_choices_missing_dose_and_bad_units_remain_visible(self):
        variants = [('productId', 'invented:product'), ('parcelId', 'invented:field'), ('cropId', '')]
        for field, value in variants:
            with self.subTest(field=field):
                capture = example(); capture[field] = value
                result = self.inbox.save(raw(capture))
                self.assertFalse(result['canAcknowledgeDraft'])
                self.assertTrue(any(item['field'] == field for item in result['issues']))
                with self.assertRaises(Problem):
                    self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': result['originalSha256']}))
                self.assert_gated(result)
        for field, value in [('value', ''), ('value', '-1'), ('value', '0,3'), ('value', 'NaN'),
                             ('value', '9007199254740993'), ('unitId', 'invented-unit')]:
            with self.subTest(dose_field=field, value=value):
                capture = example(); capture['dose'][field] = value
                self.assertFalse(self.checked(capture)['canAcknowledgeDraft'])

    def test_zero_is_visible_and_no_dose_policy_or_conversion_is_invented(self):
        capture = example(); capture['dose']['value'] = '0'
        result = self.checked(capture)
        self.assertTrue(any(item['code'] == 'ZERO_DOSE' for item in result['issues']))
        self.assertNotIn('normalizedValue', result['draftSource']['actualQuantityParameters'][0])
        self.assertTrue(any('Dose limits' in item for item in result['unresolved']))
        capture['dose'] = {'value': '1.25', 'unitId': 'kilograms-per-hectare'}
        result = self.checked(capture)
        self.assertEqual(result['draftSource']['actualQuantityParameters'][0]['quantityKindRef'], 'scheme:qudt:MassPerArea')

    def test_reversed_invalid_unknown_offset_and_mismatched_local_times(self):
        for field, value in [('end', '2026-11-11T08:00:00Z'), ('start', '2026-02-30T09:00:00Z'),
                             ('start', '2026-11-11T09:00:00-00:00'), ('startLocal', '2026-11-11T11:00'),
                             ('timeZone', 'Unknown/Zone')]:
            with self.subTest(field=field, value=value):
                capture = example(); capture['event'][field] = value
                self.assertFalse(self.checked(capture)['canAcknowledgeDraft'])
        capture = example(); capture['event']['start'] = '2026-11-11T10:00:00+01:00'
        self.assertTrue(self.checked(capture)['canAcknowledgeDraft'])

    def test_daylight_saving_gap_and_fold_are_not_guessed(self):
        for local, instant in [('2026-03-29T02:30', '2026-03-29T01:30:00Z'), ('2026-10-25T02:30', '2026-10-25T00:30:00Z')]:
            capture = example(); capture['event'].update(startLocal=local, start=instant)
            result = self.checked(capture)
            self.assertTrue(any(item['code'] == 'LOCAL_TIME_AMBIGUOUS_OR_MISSING' for item in result['issues']))

    def test_changed_catalog_cannot_silently_rebind_a_draft(self):
        capture = example(); capture['catalogSha256'] = '0' * 64
        result = self.inbox.save(raw(capture))
        self.assertIsNone(result['draftSource'])
        self.assertFalse(result['canAcknowledgeDraft'])
        self.assertIn('CATALOG_CHANGED', [v['code'] for v in result['issues']])
        self.assertEqual(result['capture']['catalogSha256'], '0' * 64)

    def test_duplicate_keys_extra_authority_flags_and_nonfinite_values_are_rejected(self):
        capture = example()
        with self.assertRaises(ValueError):
            self.inbox.save(raw(capture)[:-1] + b', "format": "spray-draft.v1"}')
        for key in ('accepted', 'payload', 'authorization', 'sourceUseApproved'):
            changed = copy.deepcopy(capture); changed[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inbox.save(raw(changed))
        with self.assertRaises(ValueError):
            self.inbox.save(raw(capture).replace(b'"0.30"', b'NaN'))

    def test_changed_stored_bytes_cannot_be_reviewed(self):
        capture = example(); self.inbox.save(raw(capture))
        with self.inbox.connect() as db:
            db.execute('UPDATE captures SET original = ? WHERE id = ?', (raw(capture) + b' ', capture['draftId']))
        with self.assertRaises(Problem):
            self.inbox.read(capture['draftId'])


class HttpBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.server = make_server(0, Path(cls.directory.name) / 'http.sqlite3', verifier=DraftOnlyVerifier())
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        cls.directory.cleanup()

    def request(self, path, data=None, headers=None):
        selected = {'Content-Type': 'application/json'} if data is not None else {}
        selected.update(headers or {})
        try:
            with urlopen(Request(self.url + path, data=data, headers=selected), timeout=10) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    def test_actual_http_entry_to_review_and_closed_publication(self):
        capture = example(); original = raw(capture)
        status, body = self.request('/api/drafts', original)
        self.assertEqual(status, 200, body)
        saved = json.loads(body)
        status, body = self.request('/api/drafts/' + capture['draftId'] + '/review', raw({'originalSha256': saved['originalSha256']}))
        self.assertEqual(status, 200, body)
        self.assertIsNotNone(json.loads(body)['reviewedAt'])
        for route in ('/commit', '/review/accept', '/api/accept', '/api/publish', '/publish', '/views/inspection-register/freeze'):
            with self.subTest(route=route):
                status, body = self.request(route, b'{}')
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(body)['gates'], GATES)

    def test_cross_origin_host_forgery_and_oversize_body(self):
        original = raw(example())
        self.assertEqual(self.request('/api/drafts', original, {'Origin': 'https://unrelated.invalid'})[0], 403)
        self.assertEqual(self.request('/api/drafts', original, {'Host': 'unrelated.invalid'})[0], 403)
        self.assertEqual(self.request('/api/drafts', b' ' * 16385)[0], 413)
        self.assertEqual(self.request('/api/drafts', original, {'Content-Type': 'text/plain'})[0], 415)

    def test_storage_failure_returns_no_success_and_no_gate_change(self):
        with patch.object(self.server.inbox, 'save', side_effect=sqlite3.OperationalError('test disk unavailable')):
            status, body = self.request('/api/drafts', raw(example()))
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)['gates'], GATES)

    def test_recheck_and_review_reject_wrong_original_before_calling_verifier(self):
        capture = example()
        self.assertEqual(self.request('/api/drafts', raw(capture))[0], 200)
        with patch.object(self.server.inbox.verifier, 'check', side_effect=AssertionError('Wrong original reached verifier')):
            for action in ('verify', 'review'):
                for digest, expected in [('0' * 64, 409), (None, 400)]:
                    with self.subTest(action=action, digest=digest):
                        status, body = self.request('/api/drafts/' + capture['draftId'] + '/' + action, raw({'originalSha256': digest}))
                        self.assertEqual(status, expected, body)


if __name__ == '__main__':
    unittest.main()
