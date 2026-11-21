"""Separate fictional amount comparisons, source traces and unchanged gates."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from app import DraftInbox, Problem
from draft import HERE, GATES, check_capture, sha
from test_draft import DraftOnlyVerifier, raw
from test_job import job_example
from verifier import Verifier, build_packet


class ExampleAmountTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        self.inbox = DraftInbox(self.root / 'drafts.sqlite3', verifier=DraftOnlyVerifier())
        self.catalog_raw = (HERE / 'catalog.json').read_bytes()
        self.catalog = json.loads(self.catalog_raw)

    def tearDown(self):
        self.directory.cleanup()

    def checked(self, capture, catalog=None):
        catalog_raw = self.catalog_raw if catalog is None else raw(catalog)
        capture = copy.deepcopy(capture); capture['catalogSha256'] = sha(catalog_raw)
        return check_capture(raw(capture), catalog_raw, '2026-11-18T23:00:00Z')

    def statuses(self, result):
        return [row['status'] for row in result['exampleAmountChecks']]

    def test_two_exact_rules_and_original_sources_survive_draft_review(self):
        capture = job_example(); original = raw(capture); saved = self.inbox.save(original)
        self.assertEqual(saved['issues'], [])
        self.assertEqual(self.statuses(saved), ['MATCH', 'MATCH'])
        for check, key, field, role, material_pointer in zip(saved['exampleAmountChecks'],
                ('product', 'water'), ('dose', 'applicationVolume'), ('PRODUCT_DOSE', 'WATER_AMOUNT'),
                ('/productId', '/applicationVolume/liquidId')):
            self.assertEqual(check['rule'], self.catalog['exampleAmountRules'][key])
            self.assertEqual(check['role'], role)
            self.assertEqual(check['ruleSource'], {'catalogRawSha256': capture['catalogSha256'], 'pointer': '/exampleAmountRules/' + key})
            self.assertEqual(check['originalSource'], {'rawSha256': sha(original), 'amountPointer': '/' + field, 'materialPointer': material_pointer})
            self.assertEqual(check['observed'], capture[field])
        reviewed = self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': saved['originalSha256']}))
        self.assertEqual(reviewed['originalText'].encode(), original)
        self.assertEqual(reviewed['exampleAmountChecks'], saved['exampleAmountChecks'])
        self.assertEqual(reviewed['gates'], GATES)
        self.assertTrue(all(row['status'] == 'NOT_EVALUATED' for row in reviewed['jobConditions']))

    def test_one_amount_cannot_make_the_other_match_and_corrections_keep_originals(self):
        for product, water, expected in [('0.31', '200.00', ['DIFFERENT', 'MATCH']),
                                         ('0.30', '201.00', ['MATCH', 'DIFFERENT']),
                                         ('0.31', '201.00', ['DIFFERENT', 'DIFFERENT']),
                                         ('0.00', '0.00', ['DIFFERENT', 'DIFFERENT'])]:
            with self.subTest(product=product, water=water):
                capture = job_example(); capture['dose']['value'] = product; capture['applicationVolume']['value'] = water
                saved = self.inbox.save(raw(capture))
                self.assertEqual(self.statuses(saved), expected)
                self.assertEqual(saved['capture'], capture)
                self.assertTrue(saved['canAcknowledgeDraft'])
                self.assertTrue(any(row['code'] == 'EXAMPLE_AMOUNT_DIFFERENCE' for row in saved['issues']))
        corrected = copy.deepcopy(capture); corrected['draftId'] = str(uuid.uuid4())
        corrected['dose']['value'] = '0.30'; corrected['applicationVolume']['value'] = '200.00'
        self.assertEqual(self.statuses(self.inbox.save(raw(corrected))), ['MATCH', 'MATCH'])
        self.assertEqual(self.inbox.read(capture['draftId'])['capture'], capture)

    def test_wrong_product_mixture_or_unit_is_unchecked_not_converted(self):
        changes = [('productId', 'binding:demo-product-b', ['NOT_CHECKED', 'MATCH']),
                   ('dose.unitId', 'kilograms-per-hectare', ['NOT_CHECKED', 'MATCH']),
                   ('applicationVolume.liquidId', 'spray-mixture', ['MATCH', 'NOT_CHECKED']),
                   ('applicationVolume.unitId', 'litres', ['MATCH', 'NOT_CHECKED'])]
        for field, value, expected in changes:
            with self.subTest(field=field):
                capture = job_example(); parts = field.split('.')
                if len(parts) == 1: capture[field] = value
                else: capture[parts[0]][parts[1]] = value
                saved = self.checked(capture)
                self.assertEqual(self.statuses(saved), expected)
                self.assertEqual(saved['capture'][parts[0]], capture[parts[0]])
        catalog = copy.deepcopy(self.catalog)
        catalog['units'][0]['ref'] = 'scheme:ucum:L'
        self.assertEqual(self.statuses(self.checked(job_example(), catalog)), ['NOT_CHECKED', 'NOT_CHECKED'])

    def test_invalid_or_lossy_amount_cannot_match_even_if_the_other_matches(self):
        for field in ('dose', 'applicationVolume'):
            for value in ('', '-1', '0,30', 'NaN', '1e2', '200.00000000000000001'):
                with self.subTest(field=field, value=value):
                    capture = job_example(); capture[field]['value'] = value
                    saved = self.checked(capture)
                    self.assertEqual(self.statuses(saved), ['NOT_CHECKED', 'MATCH'] if field == 'dose' else ['MATCH', 'NOT_CHECKED'])
                    self.assertFalse(saved['canAcknowledgeDraft'])
                    self.assertIsNone(saved['draftSource'])

    def test_decimal_equality_has_no_rounding_tolerance(self):
        capture = job_example(); capture['dose']['value'] = '0.300'; capture['applicationVolume']['value'] = '200'
        saved = self.checked(capture)
        self.assertEqual(self.statuses(saved), ['MATCH', 'MATCH'])
        self.assertEqual(saved['exampleAmountChecks'][0]['observed']['value'], '0.300')
        capture['dose']['value'] = '0.30000000000000004'
        self.assertEqual(self.statuses(self.checked(capture)), ['DIFFERENT', 'MATCH'])

    def test_missing_unsupported_or_wrong_job_rule_stays_unchecked(self):
        variants = []
        catalog = copy.deepcopy(self.catalog); del catalog['exampleAmountRules']['product']; variants.append(catalog)
        for field, value in [('comparison', 'APPROVE'), ('fictional', False), ('role', 'WATER_AMOUNT'),
                             ('jobId', 'other:job'), ('jobRevision', 'r2'), ('expected', {'value': 'NaN'})]:
            catalog = copy.deepcopy(self.catalog); catalog['exampleAmountRules']['product'][field] = value; variants.append(catalog)
        for catalog in variants:
            with self.subTest(rule=catalog['exampleAmountRules'].get('product')):
                saved = self.checked(job_example(), catalog)
                self.assertEqual(self.statuses(saved), ['NOT_CHECKED', 'MATCH'])
                self.assertTrue(any(row['code'] == 'EXAMPLE_AMOUNT_NOT_CHECKED' for row in saved['issues']))
                self.assertEqual(saved['gates'], GATES)
        for field in ('exampleAmountChecks', 'amountRulesApproved'):
            capture = job_example(); capture[field] = True
            with self.assertRaises(ValueError):
                self.inbox.save(raw(capture))

    def test_old_originals_acquire_no_rules_and_old_job_warning_is_preserved(self):
        for path in [HERE / 'fixtures/original/original.json',
                     HERE / 'fixtures/details/original.json',
                     HERE / 'fixtures/liquid/original.json',
                     HERE / 'fixtures/job/original.json']:
            with self.subTest(path=path):
                original = path.read_bytes(); saved = self.inbox.save(original)
                self.assertEqual(saved['originalText'].encode(), original)
                self.assertEqual(saved['exampleAmountChecks'], [])
                self.assertNotIn('exampleAmountChecks', build_packet(saved))
        capture = json.loads(path.read_bytes()); capture['draftId'] = str(uuid.uuid4()); capture['dose']['value'] = '0.40'
        saved = self.inbox.save(raw(capture))
        self.assertEqual(saved['exampleAmountChecks'], [])
        self.assertTrue(any(row['field'] == 'job.dose' and row['code'] == 'EXAMPLE_JOB_DIFFERENCE' for row in saved['issues']))

    def test_new_rule_version_cannot_rewrite_saved_checks(self):
        catalog_path = self.root / 'catalog.json'; catalog_path.write_bytes(self.catalog_raw)
        archive_dir = self.root / 'catalogs'; archive_dir.mkdir()
        archive = archive_dir / (sha(self.catalog_raw) + '.json'); archive.write_bytes(self.catalog_raw)
        inbox = DraftInbox(self.root / 'versions.sqlite3', catalog_path, verifier=DraftOnlyVerifier())
        capture = job_example(); first = inbox.save(raw(capture))
        updated = copy.deepcopy(self.catalog)
        updated['exampleAmountRules']['product']['revision'] = 'r2'
        updated['exampleAmountRules']['product']['expected']['value'] = '0.40'
        updated_raw = raw(updated); catalog_path.write_bytes(updated_raw)
        with patch('app.HERE', self.root):
            saved = inbox.read(capture['draftId'])
            self.assertEqual(saved['exampleAmountChecks'], first['exampleAmountChecks'])
            new = copy.deepcopy(capture); new['draftId'] = str(uuid.uuid4()); new['catalogSha256'] = sha(updated_raw)
            self.assertEqual(self.statuses(inbox.save(raw(new))), ['DIFFERENT', 'MATCH'])
            archive.unlink()
            missing = inbox.read(capture['draftId'])
            self.assertFalse(missing['canAcknowledgeDraft'])
            self.assertEqual(missing['exampleAmountChecks'], [])
            archive.write_bytes(self.catalog_raw + b' ')
            with self.assertRaises(Problem): inbox.read(capture['draftId'])


class PublicExampleAmountTests(unittest.TestCase):
    def test_real_verifier_keeps_example_results_diagnostic_and_all_gates_closed(self):
        folder = Path(os.environ.get('SPRAY_AMOUNT_RULE_TEST_EVIDENCE', HERE / '.local/test-evidence/example-amounts/public'))
        folder.mkdir(parents=True, exist_ok=True)
        capture = job_example()
        saved = check_capture(raw(capture), (HERE / 'catalog.json').read_bytes(), '2026-11-18T23:00:00Z')
        packet = build_packet(saved); checker = Verifier()
        self.assertEqual(packet['exampleAmountChecks'], saved['exampleAmountChecks'])
        atom = packet['intent']['assertionBody']['proposition']['body']
        self.assertEqual([row['parameterRole'] for row in atom['quantityParameters']], ['DOSE', 'APPLICATION_VOLUME'])
        self.assertNotIn('rate', atom['parameters'])
        self.assertEqual(atom['quantityParameters'][1]['material']['presence'], 'UNREPORTED')
        self.assertEqual(atom['quantityParameters'][1]['basis']['presence'], 'UNREPORTED')
        self.assertEqual(atom['performanceFacet'], 'OCCURRENCE')
        for field in ('intent', 'proposedResult'):
            self.assertNotIn('example-rule:', json.dumps(packet[field]))
        with patch.object(checker.transport, 'evaluate_domain', wraps=checker.transport.evaluate_domain) as actual:
            record = checker.invoke(packet)
        self.assertEqual(actual.call_args.kwargs['owner_inputs'], {})
        (folder / 'actual-response.json').write_bytes(raw(record))
        summary = checker.summary(record); (folder / 'summary.json').write_bytes(raw(summary))
        self.assertEqual(summary['state'], 'REPORT_AVAILABLE', summary)
        self.assertEqual(summary['reportStatus'], 'FAIL')
        self.assertEqual(len(summary['findings']), 49)
        self.assertIsNone(summary['payload'])
        self.assertFalse(summary['completeClaim'])
        self.assertEqual(summary['liveC4'], 'NOT_EVALUATED')
        self.assertEqual(summary['atomicCommit'], 'NOT_EVALUATED')
        self.assertEqual(summary['publication'], 'BLOCKED')
        self.assertEqual(summary['runtimeAdmission'], 'NOT_ESTABLISHED')
        changed = copy.deepcopy(packet); changed['exampleAmountChecks'][0]['rule']['expected']['value'] = '0.40'
        self.assertNotEqual(checker.identity(changed), checker.identity(packet))
        with self.assertRaises(ValueError): checker.validate(record, changed)


if __name__ == '__main__':
    unittest.main()
