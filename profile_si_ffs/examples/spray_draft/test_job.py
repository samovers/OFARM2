"""Explicit fictional work link, exact versions and no condition acceptance."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from app import DraftInbox, Problem
from draft import HERE, GATES, VALIDATOR, check_capture, sha
from test_draft import DraftOnlyVerifier, raw
from test_application_volume import liquid_example
from verifier import Verifier, binding, build_packet


def job_example():
    capture = liquid_example()
    capture.update(format='spray-draft.v4', jobId='job:demo-orchard-spray')
    return capture


class JobTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        self.inbox = DraftInbox(self.root / 'drafts.sqlite3', verifier=DraftOnlyVerifier())

    def tearDown(self):
        self.directory.cleanup()

    def test_explicit_job_and_conditions_survive_review_without_claiming_success(self):
        capture = job_example(); original = raw(capture)
        saved = self.inbox.save(original)
        expected = json.loads((HERE / 'catalog.json').read_bytes())['jobs'][0]
        self.assertEqual(saved['issues'], [])
        self.assertEqual(saved['draftJob'], expected)
        self.assertEqual(saved['jobSource'], {'catalogRawSha256': capture['catalogSha256'], 'pointer': '/jobs/0'})
        self.assertEqual(saved['jobConditions'], [{**row, 'status': 'NOT_EVALUATED'} for row in expected['conditions']])
        self.assertTrue(VALIDATOR.is_valid(saved['draftSource']))
        self.assertIn('revision r1', saved['draftSource']['actualAction']['notes'])
        self.assertIn(capture['catalogSha256'], saved['draftSource']['actualAction']['notes'])
        self.assertNotIn('workSpecification', saved['draftSource'])
        reviewed = self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': saved['originalSha256']}))
        self.assertEqual(reviewed['originalText'].encode(), original)
        self.assertEqual(reviewed['jobConditions'], saved['jobConditions'])
        self.assertEqual(reviewed['gates'], GATES)
        self.assertIsNone(reviewed['typedClaim'])
        self.assertEqual(reviewed['c3Completion'], 'NOT_CLAIMED')

    def test_missing_unknown_or_invented_success_fields_cannot_finish_review(self):
        for value in ('', 'unknown:job'):
            with self.subTest(job=value):
                capture = job_example(); capture['jobId'] = value
                saved = self.inbox.save(raw(capture))
                self.assertEqual(saved['capture'], capture)
                self.assertIsNone(saved['draftSource'])
                self.assertIsNone(saved['draftJob'])
                self.assertFalse(saved['canAcknowledgeDraft'])
                self.assertTrue(any(row['field'] == 'jobId' for row in saved['issues']))
                with self.assertRaises(Problem):
                    self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': saved['originalSha256']}))
        capture = job_example(); del capture['jobId']
        with self.assertRaises(ValueError):
            self.inbox.save(raw(capture))
        for key, value in [('jobVerified', True), ('conditionOutcomes', {'finish:O01': 'PASS'}), ('approved', True)]:
            capture = job_example(); capture[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                self.inbox.save(raw(capture))

    def test_differences_are_warnings_and_never_replace_reported_facts(self):
        capture = job_example()
        capture.update(productId='binding:demo-product-b', methodId='method:demo-handheld-sprayer',
                       treatmentTargetId='organism:demo-fungal-disease')
        capture['dose'] = {'value': '1.25', 'unitId': 'kilograms-per-hectare'}
        capture['applicationVolume'].update(liquidId='spray-mixture', value='250.50')
        saved = self.inbox.save(raw(capture))
        self.assertTrue(saved['canAcknowledgeDraft'])
        self.assertEqual(saved['capture'], capture)
        differences = [row for row in saved['issues'] if row['code'] == 'EXAMPLE_JOB_DIFFERENCE']
        self.assertEqual({row['field'] for row in differences},
                         {'job.productId', 'job.methodId', 'job.treatmentTargetId'})
        self.assertTrue(all(row['level'] == 'warning' for row in differences))
        self.assertEqual([row['status'] for row in saved['exampleAmountChecks']], ['NOT_CHECKED', 'NOT_CHECKED'])
        packet = build_packet(saved); atom = packet['intent']['assertionBody']['proposition']['body']
        self.assertEqual(atom['parameters']['product']['ref'], capture['productId'])
        self.assertEqual(atom['parameters']['method']['ref'], capture['methodId'])
        self.assertEqual(atom['parameters']['targetOrganism']['ref'], capture['treatmentTargetId'])
        self.assertEqual(atom['quantityParameters'][0]['value']['quantity']['decimal'], '1.25')
        self.assertEqual(atom['quantityParameters'][0]['value']['quantity']['unit'], 'scheme:ucum:kg/har')
        self.assertEqual(atom['quantityParameters'][1]['value']['quantity']['decimal'], '250.50')
        self.assertTrue(all(row['status'] == 'NOT_EVALUATED' for row in saved['jobConditions']))

    def test_decimal_spelling_does_not_invent_a_plan_difference(self):
        capture = job_example(); capture['dose']['value'] = '0.3'; capture['applicationVolume']['value'] = '200'
        saved = self.inbox.save(raw(capture))
        self.assertEqual(saved['issues'], [])
        self.assertEqual(saved['capture'], capture)

    def test_old_originals_acquire_no_job_and_corrected_copy_keeps_previous_original(self):
        originals = [HERE / 'fixtures/original/original.json',
                     HERE / 'fixtures/details/original.json',
                     HERE / 'fixtures/liquid/original.json']
        for path in originals:
            with self.subTest(path=path):
                original = path.read_bytes(); saved = self.inbox.save(original)
                self.assertEqual(saved['originalText'].encode(), original)
                self.assertEqual(saved['issues'], [])
                self.assertIsNone(saved['draftJob'])
                self.assertEqual(saved['jobConditions'], [])
                self.assertNotIn('workSpecification', build_packet(saved)['intent']['assertionBody']['proposition']['body'])
        first = job_example(); original = raw(first); self.inbox.save(original)
        second = copy.deepcopy(first); second['draftId'] = str(uuid.uuid4()); second['dose']['value'] = '0.40'
        corrected = self.inbox.save(raw(second))
        self.assertEqual(corrected['draftJob']['id'], first['jobId'])
        self.assertEqual(self.inbox.read(first['draftId'])['originalText'].encode(), original)
        changed = copy.deepcopy(first); changed['jobId'] = ''
        with self.assertRaises(Problem):
            self.inbox.save(raw(changed))

    def test_new_catalog_cannot_rebind_an_old_job_or_its_conditions(self):
        catalog_raw = (HERE / 'catalog.json').read_bytes()
        catalog_path = self.root / 'catalog.json'; catalog_path.write_bytes(catalog_raw)
        archives = self.root / 'catalogs'; archives.mkdir()
        archive = archives / (sha(catalog_raw) + '.json'); archive.write_bytes(catalog_raw)
        inbox = DraftInbox(self.root / 'versions.sqlite3', catalog_path, verifier=DraftOnlyVerifier())
        capture = job_example(); first = inbox.save(raw(capture))
        next_catalog = json.loads(catalog_raw)
        next_catalog['jobs'][0]['revision'] = 'r2'
        next_catalog['jobs'][0]['conditions'][2]['meaning'] = 'A changed test condition.'
        catalog_path.write_bytes(raw(next_catalog))
        with patch('app.HERE', self.root):
            saved = inbox.read(capture['draftId'])
            self.assertEqual(saved['draftJob'], first['draftJob'])
            self.assertEqual(saved['jobConditions'], first['jobConditions'])
            self.assertEqual(saved['originalText'], first['originalText'])
            archive.unlink()
            missing = inbox.read(capture['draftId'])
            self.assertFalse(missing['canAcknowledgeDraft'])
            self.assertIsNone(missing['draftJob'])
            self.assertEqual(missing['jobConditions'], [])
            archive.write_bytes(catalog_raw + b' ')
            with self.assertRaises(Problem):
                inbox.read(capture['draftId'])

    def test_proposal_links_exact_fictional_job_without_completion_or_admission(self):
        saved = self.inbox.save(raw(job_example())); before = copy.deepcopy(saved)
        packet = build_packet(saved); atom = packet['intent']['assertionBody']['proposition']['body']
        job = saved['draftJob']; work = atom['workSpecification']
        self.assertEqual(saved, before)
        self.assertEqual(packet['draftJob'], job)
        self.assertEqual(packet['jobSource'], saved['jobSource'])
        self.assertEqual(packet['jobConditions'], saved['jobConditions'])
        self.assertEqual(work['binding'], binding(job['id'], job))
        self.assertEqual(work['procedure'], binding(job['procedure']['id'], job['procedure']))
        self.assertEqual(work['activityInstance'], {'ref': job['activityInstanceRef']})
        self.assertEqual(atom['activityInstance'], work['activityInstance'])
        self.assertEqual(work['target'], atom['target'])
        self.assertEqual(work['extent'], atom['extent'])
        for field, expected in [('startConditionIds', ['start:O01']),
                                ('inProgressConditionIds', ['progress:O01']), ('finishConditionIds', ['finish:O01'])]:
            self.assertEqual(work[field], expected)
        self.assertEqual(atom['performanceFacet'], 'OCCURRENCE')
        self.assertNotIn('overallWorkCoverage', atom)
        for quantity in atom['quantityParameters']:
            self.assertEqual(quantity['activityInstance'], work['activityInstance'])
        self.assertEqual(packet['proposedResult']['assertionBody'], packet['intent']['assertionBody'])
        self.assertNotIn('evaluationSelection', packet['intent'])
        self.assertNotIn('ownerInputs', packet)
        self.assertIn('conditions have not been verified', packet['missingInputs'][3]['message'])
        checker = Verifier(); changed = copy.deepcopy(saved)
        changed['draftJob']['conditions'][2]['meaning'] = 'Different fictional finish criterion.'
        self.assertNotEqual(checker.identity(packet), checker.identity(build_packet(changed)))


class PublicJobTests(unittest.TestCase):
    def test_actual_verifier_copies_job_and_detects_changed_binding_or_condition(self):
        folder = Path(os.environ.get('SPRAY_JOB_TEST_EVIDENCE', HERE / '.local/test-evidence/job/public'))
        folder.mkdir(parents=True, exist_ok=True)
        draft = check_capture(raw(job_example()), (HERE / 'catalog.json').read_bytes(), '2026-11-18T19:00:00Z')
        checker = Verifier(); packet = build_packet(draft); record = checker.invoke(packet)
        (folder / 'actual-response.json').write_bytes(raw(record))
        summary = checker.summary(record); (folder / 'summary.json').write_bytes(raw(summary))
        self.assertEqual(summary['state'], 'REPORT_AVAILABLE', summary)
        finding = next(row for row in summary['findings'] if row['id'] == 'AR_BODY')
        self.assertTrue(next(row for row in finding['comparisons'] if row['predicateId'] == 'mapping.assertionBody')['equal'])
        self.assertFalse(summary['completeClaim'])
        self.assertIsNone(summary['payload'])
        self.assertEqual(summary['liveC4'], 'NOT_EVALUATED')
        self.assertEqual(summary['publication'], 'BLOCKED')
        for variant in ('binding', 'condition'):
            with self.subTest(variant=variant):
                changed = copy.deepcopy(packet)
                work = changed['proposedResult']['assertionBody']['proposition']['body']['workSpecification']
                if variant == 'binding': work['binding']['digest'] = 'sha256:' + '0' * 64
                else: work['finishConditionIds'] = ['finish:invented']
                response = checker.invoke(changed)
                (folder / ('actual-changed-' + variant + '-response.json')).write_bytes(raw(response))
                report = response['response']['domainReport']
                finding = next(row for row in report['mappingFindings'] if row['id'] == 'AR_BODY')
                self.assertTrue(any(row['code'] == 'COPY_MISMATCH' and row.get('detail') == 'mapping.assertionBody'
                                    for row in finding['diagnostics']))
                self.assertIsNone(report['payload'])
                self.assertEqual(report['atomicCommit'], 'NOT_EVALUATED')
                self.assertEqual(report['runtimeAdmission'], 'NOT_ESTABLISHED')


if __name__ == '__main__':
    unittest.main()
