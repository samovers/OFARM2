"""Explicit fictional note links; no admitted evidence or condition success."""
import copy
import hashlib
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


def evidence_example():
    value = job_example()
    value.update(format='spray-draft.v5', exampleEvidenceSetId='example-evidence:orchard-notes:r1')
    return value


class ConditionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.root = Path(self.directory.name).resolve()
        self.inbox = DraftInbox(self.root / 'drafts.sqlite3', verifier=DraftOnlyVerifier())
        self.catalog_raw = (HERE / 'catalog.json').read_bytes(); self.catalog = json.loads(self.catalog_raw)

    def tearDown(self):
        self.directory.cleanup()

    def checked(self, capture=None, catalog=None):
        capture = copy.deepcopy(capture or evidence_example())
        catalog_raw = self.catalog_raw if catalog is None else raw(catalog)
        capture['catalogSha256'] = sha(catalog_raw)
        return check_capture(raw(capture), catalog_raw, '2026-11-18T23:00:00Z')

    def statuses(self, result):
        return [row['status'] for row in result['exampleConditionEvidence']['links']]

    def test_explicit_notes_link_separately_with_exact_text_and_original_pointers(self):
        capture = evidence_example(); original = raw(capture); saved = self.inbox.save(original)
        self.assertEqual(saved['issues'], [])
        selected = saved['exampleConditionEvidence']
        self.assertEqual(selected['evidenceSet'], self.catalog['exampleEvidenceSets'][0])
        self.assertEqual(self.statuses(saved), ['EXAMPLE_LINKED'] * 3)
        self.assertEqual(selected['source'], {'catalogRawSha256': capture['catalogSha256'], 'pointer': '/exampleEvidenceSets/0'})
        for i, link in enumerate(selected['links']):
            note = self.catalog['exampleEvidenceSets'][0]['records'][i]
            self.assertEqual(link['record'], note)
            self.assertEqual(link['conditionId'], saved['jobConditions'][i]['id'])
            self.assertEqual(link['conditionStatus'], 'NOT_EVALUATED')
            self.assertEqual(link['source'], {'catalogRawSha256': capture['catalogSha256'], 'pointer': '/exampleEvidenceSets/0/records/' + str(i)})
            self.assertEqual(note['originalTextSha256'], hashlib.sha256(note['originalText'].encode()).hexdigest())
            self.assertIn('FICTIONAL EXAMPLE', note['originalText'])
        reviewed = self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': saved['originalSha256']}))
        self.assertEqual(reviewed['originalText'].encode(), original)
        self.assertEqual(reviewed['exampleConditionEvidence'], selected)
        self.assertEqual(reviewed['gates'], GATES)
        self.assertEqual(selected['evidenceUse'], 'NOT_ADMITTED')
        self.assertTrue(all(row['status'] == 'NOT_EVALUATED' for row in reviewed['jobConditions']))

    def test_empty_choice_is_explicit_unknown_choice_and_success_flags_cannot_pass(self):
        capture = evidence_example(); capture['exampleEvidenceSetId'] = ''
        saved = self.inbox.save(raw(capture))
        self.assertTrue(saved['canAcknowledgeDraft'])
        self.assertEqual(self.statuses(saved), ['NO_EXAMPLE'] * 3)
        capture = evidence_example(); capture['exampleEvidenceSetId'] = 'unknown:notes'
        saved = self.inbox.save(raw(capture))
        self.assertFalse(saved['canAcknowledgeDraft'])
        self.assertIsNone(saved['draftSource'])
        self.assertEqual(saved['capture'], capture)
        with self.assertRaises(Problem):
            self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': saved['originalSha256']}))
        capture = evidence_example(); del capture['exampleEvidenceSetId']
        with self.assertRaises(ValueError): self.inbox.save(raw(capture))
        for field in ('evidenceApproved', 'jobConditions', 'exampleConditionEvidence'):
            capture = evidence_example(); capture[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError): self.inbox.save(raw(capture))

    def test_different_person_product_place_method_target_or_time_cannot_reuse_notes(self):
        changes = [('performerId', 'party:demo-farmer'), ('productId', 'binding:demo-product-b'),
                   ('parcelId', 'field:another'), ('cropId', 'crop:another'),
                   ('methodId', 'method:demo-handheld-sprayer'), ('treatmentTargetId', 'organism:demo-fungal-disease')]
        for field, value in changes:
            with self.subTest(field=field):
                capture = evidence_example(); capture[field] = value
                saved = self.checked(capture)
                self.assertEqual(self.statuses(saved), ['CONTEXT_MISMATCH'] * 3)
                self.assertTrue(all(row['record'] is None for row in saved['exampleConditionEvidence']['links']))
        capture = evidence_example(); capture['event'].update(start='2026-11-11T09:01:00Z', startLocal='2026-11-11T10:01')
        self.assertEqual(self.statuses(self.checked(capture)), ['CONTEXT_MISMATCH'] * 3)
        for field in ('jobRevision', 'activityInstanceRef'):
            catalog = copy.deepcopy(self.catalog); catalog['exampleEvidenceSets'][0][field] = 'different'
            self.assertEqual(self.statuses(self.checked(catalog=catalog)), ['CONTEXT_MISMATCH'] * 3)

    def test_equivalent_instants_match_but_notes_do_not_prove_amounts(self):
        capture = evidence_example()
        capture['event'].update(start='2026-11-11T10:00:00.000+01:00', end='2026-11-11T10:45:00+01:00')
        capture['dose']['value'] = '0.31'
        saved = self.checked(capture)
        self.assertEqual(self.statuses(saved), ['EXAMPLE_LINKED'] * 3)
        self.assertEqual(saved['exampleAmountChecks'][0]['status'], 'DIFFERENT')
        self.assertIn('amounts', saved['exampleConditionEvidence']['links'][1]['record']['limitations'])

    def test_missing_note_does_not_borrow_another_conditions_evidence(self):
        catalog = copy.deepcopy(self.catalog); catalog['exampleEvidenceSets'][0]['records'].pop(1)
        saved = self.checked(catalog=catalog)
        self.assertEqual(self.statuses(saved), ['EXAMPLE_LINKED', 'NO_EXAMPLE', 'EXAMPLE_LINKED'])
        finish = saved['exampleConditionEvidence']['links'][2]
        self.assertIn('every selected treatment segment is still missing', finish['record']['limitations'])
        self.assertEqual(finish['source']['pointer'], '/exampleEvidenceSets/0/records/1')
        atom = build_packet(saved)['intent']['assertionBody']['proposition']['body']
        self.assertEqual(atom['performanceFacet'], 'OCCURRENCE')
        self.assertNotIn('overallWorkCoverage', atom['parameters'])

    def test_changed_nonfiction_wrong_condition_or_out_of_time_note_is_not_linked(self):
        for field, value in [('originalText', 'Altered original without matching digest'), ('fictional', False),
                             ('phase', 'FINISH'), ('conditionMeaning', 'Changed meaning'),
                             ('observedAt', '2026-11-11T08:59:59Z'), ('observedAt', 'not-a-time')]:
            with self.subTest(field=field, value=value):
                catalog = copy.deepcopy(self.catalog); catalog['exampleEvidenceSets'][0]['records'][0][field] = value
                self.assertEqual(self.statuses(self.checked(catalog=catalog)), ['INVALID_EXAMPLE', 'EXAMPLE_LINKED', 'EXAMPLE_LINKED'])
        catalog = copy.deepcopy(self.catalog); catalog['exampleEvidenceSets'][0]['records'][0]['conditionId'] = 'unknown:condition'
        saved = self.checked(catalog=catalog)
        self.assertEqual(self.statuses(saved), ['NO_EXAMPLE', 'EXAMPLE_LINKED', 'EXAMPLE_LINKED'])
        self.assertTrue(any(row['code'] == 'UNKNOWN_EXAMPLE_CONDITION' for row in saved['issues']))
        catalog = copy.deepcopy(self.catalog); catalog['exampleEvidenceSets'][0]['fictional'] = False
        self.assertEqual(self.statuses(self.checked(catalog=catalog)), ['INVALID_EXAMPLE'] * 3)

    def test_duplicate_ids_or_condition_links_are_ambiguous(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['exampleEvidenceSets'][0]['records'].append(copy.deepcopy(catalog['exampleEvidenceSets'][0]['records'][0]))
        self.assertEqual(self.statuses(self.checked(catalog=catalog)), ['INVALID_EXAMPLE', 'EXAMPLE_LINKED', 'EXAMPLE_LINKED'])
        catalog = copy.deepcopy(self.catalog)
        catalog['exampleEvidenceSets'][0]['records'][0]['id'] = catalog['exampleEvidenceSets'][0]['records'][1]['id']
        self.assertEqual(self.statuses(self.checked(catalog=catalog)), ['INVALID_EXAMPLE', 'INVALID_EXAMPLE', 'EXAMPLE_LINKED'])
        catalog = copy.deepcopy(self.catalog); catalog['exampleEvidenceSets'].append(copy.deepcopy(catalog['exampleEvidenceSets'][0]))
        saved = self.checked(catalog=catalog)
        self.assertFalse(saved['canAcknowledgeDraft'])
        self.assertEqual(self.statuses(saved), ['NO_EXAMPLE'] * 3)

    def test_old_originals_acquire_no_notes_and_corrected_copy_keeps_old_selection(self):
        for path in [HERE / 'fixtures/original/original.json',
                     HERE / 'fixtures/details/original.json',
                     HERE / 'fixtures/liquid/original.json',
                     HERE / 'fixtures/job/original.json',
                     HERE / 'fixtures/amount-rules/original.json']:
            with self.subTest(path=path):
                original = path.read_bytes(); saved = self.inbox.save(original)
                self.assertEqual(saved['originalText'].encode(), original)
                self.assertIsNone(saved['exampleConditionEvidence'])
                self.assertNotIn('exampleConditionEvidence', build_packet(saved))
        first = evidence_example(); original = raw(first); self.inbox.save(original)
        second = copy.deepcopy(first); second.update(draftId=str(uuid.uuid4()), exampleEvidenceSetId='')
        self.assertEqual(self.statuses(self.inbox.save(raw(second))), ['NO_EXAMPLE'] * 3)
        self.assertEqual(self.inbox.read(first['draftId'])['originalText'].encode(), original)
        with self.assertRaises(Problem):
            changed = copy.deepcopy(first); changed['exampleEvidenceSetId'] = ''; self.inbox.save(raw(changed))

    def test_new_note_version_cannot_rewrite_saved_originals_or_links(self):
        catalog_path = self.root / 'catalog.json'; catalog_path.write_bytes(self.catalog_raw)
        archives = self.root / 'catalogs'; archives.mkdir()
        archive = archives / (sha(self.catalog_raw) + '.json'); archive.write_bytes(self.catalog_raw)
        inbox = DraftInbox(self.root / 'versions.sqlite3', catalog_path, verifier=DraftOnlyVerifier())
        capture = evidence_example(); first = inbox.save(raw(capture))
        updated = copy.deepcopy(self.catalog); notes = updated['exampleEvidenceSets'][0]
        notes.update(id='example-evidence:orchard-notes:r2', revision='r2')
        notes['records'][0]['originalText'] += ' FICTIONAL revision 2.'
        notes['records'][0]['originalTextSha256'] = sha(notes['records'][0]['originalText'].encode())
        updated_raw = raw(updated); catalog_path.write_bytes(updated_raw)
        with patch('app.HERE', self.root):
            self.assertEqual(inbox.read(capture['draftId'])['exampleConditionEvidence'], first['exampleConditionEvidence'])
            new = copy.deepcopy(capture); new.update(draftId=str(uuid.uuid4()), catalogSha256=sha(updated_raw), exampleEvidenceSetId=notes['id'])
            saved = inbox.save(raw(new))
            self.assertEqual(self.statuses(saved), ['EXAMPLE_LINKED'] * 3)
            self.assertNotEqual(saved['exampleConditionEvidence']['links'][0]['record'], first['exampleConditionEvidence']['links'][0]['record'])
            archive.unlink()
            stale = inbox.read(capture['draftId'])
            self.assertFalse(stale['canAcknowledgeDraft'])
            self.assertEqual(stale['exampleConditionEvidence']['links'], [])
            archive.write_bytes(self.catalog_raw + b' ')
            with self.assertRaises(Problem): inbox.read(capture['draftId'])


class PublicConditionEvidenceTests(unittest.TestCase):
    def test_real_verifier_receives_no_fictional_owner_evidence_or_completion_claim(self):
        folder = Path(os.environ.get('SPRAY_CONDITION_EVIDENCE_TEST_EVIDENCE', HERE / '.local/test-evidence/condition-evidence/public'))
        folder.mkdir(parents=True, exist_ok=True)
        capture = evidence_example()
        saved = check_capture(raw(capture), (HERE / 'catalog.json').read_bytes(), '2026-11-18T23:00:00Z')
        packet = build_packet(saved); checker = Verifier()
        self.assertEqual(packet['exampleConditionEvidence'], saved['exampleConditionEvidence'])
        self.assertEqual(saved['draftSource']['evidenceRefs'], [saved['draftEvidence']['evidenceRecordId']])
        self.assertEqual(len(packet['intent']['evidenceBindings']), 2)
        for field in ('intent', 'proposedResult'):
            self.assertNotIn('example-note:', json.dumps(packet[field]))
            self.assertNotIn('example-evidence:', json.dumps(packet[field]))
            atom = packet[field]['assertionBody']['proposition']['body']
            self.assertEqual(atom['performanceFacet'], 'OCCURRENCE')
            self.assertNotIn('overallWorkCoverage', atom['parameters'])
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
        self.assertEqual(summary['runtimeAdmission'], 'NOT_ESTABLISHED')
        self.assertEqual(summary['publication'], 'BLOCKED')
        changed = copy.deepcopy(packet); changed['exampleConditionEvidence']['links'][0]['record']['originalText'] = 'Different note'
        self.assertNotEqual(checker.identity(changed), checker.identity(packet))
        with self.assertRaises(ValueError): checker.validate(record, changed)


if __name__ == '__main__':
    unittest.main()
