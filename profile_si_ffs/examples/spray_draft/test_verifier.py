"""Narrow draft/real-verifier integration and refusal tests; no C3 closure."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from draft import HERE, check_capture
from test_draft import example, raw as capture_raw
from verifier import ACTION, Verifier, build_packet, raw


class VerifierIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.cache = Path(cls.directory.name)
        cls.capture = example()
        cls.draft = check_capture(capture_raw(cls.capture), (HERE / 'catalog.json').read_bytes(), '2026-11-12T12:00:00Z')
        cls.checker = Verifier()
        cls.packet = build_packet(cls.draft)
        cls.summary = cls.checker.check(cls.draft, cls.cache)
        cls.evidence = Path(os.environ.get('SPRAY_TEST_EVIDENCE', HERE / '.local/test-evidence/verifier-integration'))
        cls.evidence.mkdir(parents=True, exist_ok=True)
        (cls.evidence / 'current-call-summary.json').write_bytes(raw(cls.summary))
        if cls.summary['state'] != 'REPORT_AVAILABLE':
            for attempt in cls.cache.glob('attempt-*.json'):
                (cls.evidence / 'actual-blocked-response.json').write_bytes(attempt.read_bytes())
            cls.directory.cleanup()
            raise unittest.SkipTest('Actual report tests blocked by the verifier: ' + cls.summary.get('error', cls.summary['message']))
        cls.record = json.loads((cls.cache / (cls.checker.identity(cls.packet) + '.json')).read_bytes())
        (cls.evidence / 'actual-draft-response.json').write_bytes(raw(cls.record))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_actual_public_response_has_all_49_findings_and_closed_gates(self):
        self.assertEqual(self.summary['state'], 'REPORT_AVAILABLE')
        self.assertEqual(len(self.summary['findings']), 49)
        self.assertEqual(sum(self.summary['counts'].values()), 49)
        self.assertEqual(self.summary['reportStatus'], 'FAIL')
        self.assertEqual(self.summary['implementationCompleteness'], 'INCOMPLETE')
        self.assertEqual(self.summary['atomicCommit'], 'NOT_EVALUATED')
        self.assertEqual(self.summary['runtimeAdmission'], 'NOT_ESTABLISHED')
        self.assertIsNone(self.summary['payload'])
        self.assertFalse(self.summary['completeClaim'])
        self.assertEqual(self.summary['publication'], 'BLOCKED')
        imported = self.record['response']['importsAfterChecker']
        self.assertTrue(any(row['module'] == 'verify_domain' and row['path'] == str(self.checker.root / 'verify_domain.py') for row in imported))
        self.assertEqual(self.record['response']['transport']['returnCode'], 0)

    def test_known_source_schema_metadata_reaches_verifier(self):
        self.assertFalse(any('/executionRecordPayloadBindings' in row['pointer'] for group in self.summary['schemaFindings'].values() for row in group))

    def test_retry_reuses_exact_checked_result_without_another_worker(self):
        with patch.object(self.checker.transport, 'evaluate_domain', side_effect=AssertionError('Unexpected worker retry')):
            result = self.checker.check(self.draft, self.cache)
        self.assertTrue(result['fromCache'])
        self.assertEqual(result['checkId'], self.summary['checkId'])
        self.assertEqual(result['checkedAtUtc'], self.summary['checkedAtUtc'])

    def test_a_report_from_another_draft_or_changed_code_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed['captureOriginalSha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.checker.validate(self.record, changed)
        changed_record = copy.deepcopy(self.record)
        changed_record['adapterSha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.checker.validate(changed_record, self.packet)

    def test_invented_success_or_payload_is_rejected(self):
        for field, value in [('payload', {'approved': True}), ('atomicCommit', 'PASS'),
                             ('runtimeAdmission', 'ESTABLISHED'), ('implementationCompleteness', 'COMPLETE'), ('status', 'PASS')]:
            with self.subTest(field=field):
                record = copy.deepcopy(self.record)
                record['response']['domainReport'][field] = value
                with self.assertRaises(ValueError):
                    self.checker.validate(record, self.packet)

    def test_report_and_transport_mutation_cannot_masquerade_as_worker_output(self):
        variants = []
        record = copy.deepcopy(self.record)
        record['response']['domainReport']['mappingFindings'][0]['disposition'] = 'FORGED'; variants.append(record)
        record = copy.deepcopy(self.record)
        record['response']['transport']['requestRawSha256'] = '0' * 64; variants.append(record)
        record = copy.deepcopy(self.record)
        record['response']['domainReport']['inputBindings']['effectIntent']['rawSha256'] = '0' * 64; variants.append(record)
        record = copy.deepcopy(self.record)
        record['response']['domainReport']['postconditionFindings'].pop(); variants.append(record)
        for index, record in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.checker.validate(record, self.packet)

    def test_changed_proposed_dose_reaches_real_body_copy_failure(self):
        packet = copy.deepcopy(self.packet)
        packet['proposedResult']['assertionBody']['proposition']['body']['quantityParameters'][0]['value']['quantity']['decimal'] = '0.99'
        record = self.checker.invoke(packet)
        (self.evidence / 'actual-changed-dose-response.json').write_bytes(raw(record))
        report = record['response']['domainReport']
        finding = next(row for row in report['mappingFindings'] if row['id'] == 'AR_BODY')
        self.assertTrue(any(row['code'] == 'COPY_MISMATCH' and row.get('detail') == 'mapping.assertionBody' for row in finding['diagnostics']))
        baseline = next(row for row in self.record['response']['domainReport']['mappingFindings'] if row['id'] == 'AR_BODY')
        self.assertFalse(any(row['code'] == 'COPY_MISMATCH' and row.get('detail') == 'mapping.assertionBody' for row in baseline['diagnostics']))
        self.assertIsNone(report['payload'])

    def test_real_wrong_pin_is_unavailable_and_not_a_success(self):
        packet = self.packet
        failure = self.checker.transport.evaluate_domain(raw(packet['intent']), raw(packet['proposedResult']),
            package={'root': str(self.checker.root), 'manifestRawSha256': '0' * 64, 'selectedAction': ACTION}, owner_inputs={})
        (self.evidence / 'actual-wrong-pin-response.json').write_bytes(raw(failure))
        self.assertEqual(failure['status'], 'DEPENDENCY_INTEGRITY_ERROR')
        self.assertNotIn('domainReport', failure)
        with tempfile.TemporaryDirectory() as directory, patch.object(self.checker.transport, 'evaluate_domain', return_value=failure):
            projected = self.checker.check(self.draft, directory)
            self.assertEqual(projected['state'], 'UNAVAILABLE')
            self.assertEqual(projected['findings'], [])
            self.assertFalse(projected['completeClaim'])


class DraftMappingTests(unittest.TestCase):
    def setUp(self):
        self.capture = example()
        self.draft = check_capture(capture_raw(self.capture), (HERE / 'catalog.json').read_bytes(), '2026-11-12T12:00:00Z')
        self.packet = build_packet(self.draft)
        self.checker = Verifier()

    def test_only_available_facts_are_mapped_without_trusted_time_or_performer(self):
        intent = self.packet['intent']; result = self.packet['proposedResult']; body = intent['assertionBody']
        atom = body['proposition']['body']; quantity = atom['quantityParameters'][0]
        for key in ('assertionActPosture', 'assertedAt', 'performedByPartyRef', 'assertionActEvidenceBinding', 'associatedSemanticEventBinding'):
            self.assertNotIn(key, intent)
        self.assertNotIn('assertedAt', result)
        for key in ('workSpecification', 'activityInstance', 'performedBy'):
            self.assertNotIn(key, atom)
        self.assertEqual(set(atom['parameters']), {'product'})
        self.assertEqual(quantity['parameterRole'], 'DOSE')
        self.assertEqual(quantity['value']['original']['lexicalValue'], '0.30')
        self.assertEqual(intent['subjectTime']['start'], self.capture['event']['start'])
        self.assertNotIn('rate', atom['parameters'])
        self.assertNotIn('applicationVolume', atom['parameters'])
        self.assertNotIn('claimText', body)
        source_declaration = body['executionRecordPayloadBindings'][0]
        self.assertEqual(source_declaration['schemaDigest'], 'sha256:ca62f01d056794ee588d55c3f5df652fc039124b76af5631d417714bc7059ff0')

    def test_source_and_saved_entry_are_bound_without_modifying_them(self):
        before = copy.deepcopy(self.draft)
        packet = build_packet(self.draft)
        self.assertEqual(self.draft, before)
        self.assertEqual(packet['captureOriginalSha256'], before['originalSha256'])
        self.assertEqual(packet['draftSource'], before['draftSource'])
        self.assertEqual(packet['draftEvidence'], before['draftEvidence'])
        changed = copy.deepcopy(packet)
        changed['captureOriginalSha256'] = '0' * 64
        self.assertNotEqual(self.checker.identity(changed), self.checker.identity(packet))

    def test_invalid_entry_is_not_sent_to_the_verifier(self):
        draft = copy.deepcopy(self.draft); draft['draftSource'] = None
        with patch.object(self.checker.transport, 'evaluate_domain', side_effect=AssertionError('Invalid draft was sent')):
            result = self.checker.check(draft, HERE / 'unused-test-cache')
        self.assertEqual(result['state'], 'NOT_RUN')

    def test_corrupt_saved_report_stays_unavailable_and_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (self.checker.identity(self.packet) + '.json')
            damaged = {'checkId': 'belongs-to-another-draft', 'response': {'status': 'DOMAIN_REPORT'}}
            path.write_bytes(raw(damaged)); original = path.read_bytes()
            with patch.object(self.checker.transport, 'evaluate_domain', side_effect=AssertionError('Unexpected retry over corrupted record')):
                result = self.checker.check(self.draft, directory)
            self.assertEqual(result['state'], 'UNAVAILABLE')
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
