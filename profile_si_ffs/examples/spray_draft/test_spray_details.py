"""Three reported details, original preservation and the unchanged public gate."""
import copy
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app import DraftInbox, Problem
from draft import HERE, GATES, VALIDATOR, check_capture, sha
from test_draft import DraftOnlyVerifier, example, raw
from verifier import Verifier, build_packet

OLD_CATALOG = HERE / 'catalogs/6561334cff8495294b4dd72cd85ff1c9306e616a0e445fa74507c7ad34ae564a.json'


def detailed_example():
    value = example()
    value.update(format='spray-draft.v2', performerId='party:demo-operator',
                 methodId='method:demo-tractor-sprayer', treatmentTargetId='organism:demo-pest')
    return value


class SprayDetailsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.inbox = DraftInbox(self.root / 'drafts.sqlite3', verifier=DraftOnlyVerifier())

    def tearDown(self):
        self.directory.cleanup()

    def test_three_details_survive_save_read_review_and_keep_recorder_separate(self):
        capture = detailed_example(); original = raw(capture)
        saved = self.inbox.save(original)
        self.assertEqual(saved['issues'], [])
        self.assertEqual(saved['originalText'].encode(), original)
        self.assertEqual(saved['capture'], capture)
        source = saved['draftSource']
        self.assertTrue(VALIDATOR.is_valid(source))
        self.assertEqual(source['actor']['actorPartyRef'], 'party:demo-farmer')
        self.assertEqual(source['actor']['operatorPartyRef'], capture['performerId'])
        self.assertEqual(saved['draftEvidence']['capturedByPartyRef'], 'party:demo-farmer')
        self.assertEqual(source['actualAction']['methodRef'], capture['methodId'])
        self.assertNotIn('targetOrganism', source['actualAction'])
        self.assertNotIn(capture['treatmentTargetId'], source['agronomicIdentityBindingRefs'])
        reviewed = self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': saved['originalSha256']}))
        self.assertEqual(reviewed['capture'], capture)
        self.assertEqual(reviewed['gates'], GATES)
        self.assertEqual(self.inbox.read(capture['draftId'])['displayLabels']['performers']['label'], 'Example operator')

    def test_blank_and_unknown_choices_stay_saved_and_block_draft_review(self):
        for field in ('performerId', 'methodId', 'treatmentTargetId'):
            for value in ('', 'invented:choice'):
                with self.subTest(field=field, value=value):
                    capture = detailed_example(); capture[field] = value
                    original = raw(capture); saved = self.inbox.save(original)
                    self.assertEqual(saved['originalText'].encode(), original)
                    self.assertIsNone(saved['draftSource'])
                    self.assertFalse(saved['canAcknowledgeDraft'])
                    self.assertTrue(any(row['field'] == field for row in saved['issues']))
                    with self.assertRaises(Problem):
                        self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': saved['originalSha256']}))

    def test_v2_requires_explicit_fields_and_cannot_smuggle_authority(self):
        for field in ('performerId', 'methodId', 'treatmentTargetId'):
            capture = detailed_example(); del capture[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.inbox.save(raw(capture))
        capture = detailed_example(); capture['performerVerified'] = True
        with self.assertRaises(ValueError):
            self.inbox.save(raw(capture))

    def test_old_catalog_and_original_are_preserved_without_defaulting_new_details(self):
        original = (HERE / 'fixtures/original/original.json').read_bytes()
        saved = self.inbox.save(original)
        self.assertEqual(saved['issues'], [])
        self.assertEqual(saved['originalText'].encode(), original)
        self.assertEqual(saved['capture']['catalogSha256'], sha(OLD_CATALOG.read_bytes()))
        self.assertNotEqual(saved['capture']['catalogSha256'], sha((HERE / 'catalog.json').read_bytes()))
        self.assertNotIn('operatorPartyRef', saved['draftSource']['actor'])
        self.assertNotIn('methodRef', saved['draftSource']['actualAction'])
        packet = build_packet(saved)
        self.assertNotIn('performedByPartyRef', packet['intent'])
        self.assertEqual(set(packet['intent']['assertionBody']['proposition']['body']['parameters']), {'product'})
        self.assertEqual(saved['displayLabels']['products']['label'], 'Example product A')

    def test_damaged_archived_catalog_cannot_be_used_for_a_saved_original(self):
        archive = self.root / 'catalogs'; archive.mkdir()
        catalog_path = self.root / 'catalog.json'; catalog_path.write_bytes((HERE / 'catalog.json').read_bytes())
        (archive / OLD_CATALOG.name).write_bytes(OLD_CATALOG.read_bytes() + b' ')
        capture = example(); capture['catalogSha256'] = OLD_CATALOG.stem
        inbox = DraftInbox(self.root / 'archive.sqlite3', catalog_path, verifier=DraftOnlyVerifier())
        with patch('app.HERE', self.root.resolve()), self.assertRaises(Problem) as raised:
            inbox.save(raw(capture))
        self.assertEqual(raised.exception.status, 409)
        with inbox.connect() as db:
            self.assertEqual(bytes(db.execute('SELECT original FROM captures').fetchone()[0]), raw(capture))

    def test_corrected_copy_changes_details_without_rewriting_original(self):
        first = detailed_example(); first_raw = raw(first); self.inbox.save(first_raw)
        second = copy.deepcopy(first)
        second.update(draftId=str(uuid.uuid4()), performerId='party:demo-farmer',
                      methodId='method:demo-handheld-sprayer', treatmentTargetId='organism:demo-fungal-disease')
        saved = self.inbox.save(raw(second))
        self.assertEqual(self.inbox.read(first['draftId'])['originalText'].encode(), first_raw)
        self.assertEqual(saved['capture'], second)
        self.assertEqual(saved['draftSource']['actor']['operatorPartyRef'], 'party:demo-farmer')

    def test_only_entered_references_reach_proposal_with_traceable_origins(self):
        capture = detailed_example()
        draft = check_capture(raw(capture), (HERE / 'catalog.json').read_bytes(), '2026-11-12T12:00:00Z')
        packet = build_packet(draft); intent = packet['intent']; result = packet['proposedResult']
        body = intent['assertionBody']; atom = body['proposition']['body']
        self.assertEqual(packet['capture'], capture)
        self.assertEqual(intent['performedByPartyRef'], draft['draftSource']['actor']['operatorPartyRef'])
        self.assertEqual(body['performedByBinding'], {'ref': capture['performerId']})
        self.assertEqual(atom['performedBy'], body['performedByBinding'])
        self.assertEqual(result['operationClaimContext']['performedByPartyRef'], capture['performerId'])
        self.assertEqual(result['assertionBody'], body)
        self.assertEqual(atom['parameters']['method'], {'ref': draft['draftSource']['actualAction']['methodRef']})
        self.assertEqual(atom['parameters']['targetOrganism'], {'ref': packet['capture']['treatmentTargetId']})
        self.assertNotIn('assertedAt', intent)
        self.assertNotIn('workSpecification', atom)
        self.assertNotIn('rate', atom['parameters'])
        self.assertNotIn('applicationVolume', atom['parameters'])
        self.assertNotIn('claimText', body)
        self.assertEqual(atom['quantityParameters'][0]['parameterRole'], 'DOSE')
        self.assertIn('still need verification', packet['missingInputs'][2]['message'])
        self.assertIn('versioned definitions', packet['missingInputs'][3]['message'])
        changed = copy.deepcopy(draft); changed['capture']['treatmentTargetId'] = 'organism:demo-fungal-disease'
        checker = Verifier()
        self.assertNotEqual(checker.identity(packet), checker.identity(build_packet(changed)))


class PublicSprayDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture = detailed_example()
        cls.draft = check_capture(raw(cls.capture), (HERE / 'catalog.json').read_bytes(), '2026-11-12T12:00:00Z')
        cls.checker = Verifier()
        cls.folder = Path(os.environ.get('SPRAY_DETAILS_TEST_EVIDENCE', HERE / '.local/test-evidence/spray-details-20261118/public'))
        cls.folder.mkdir(parents=True, exist_ok=True)
        cls.record = cls.checker.invoke(build_packet(cls.draft))
        (cls.folder / 'actual-response.json').write_bytes(raw(cls.record))
        cls.summary = cls.checker.summary(cls.record)
        (cls.folder / 'summary.json').write_bytes(raw(cls.summary))

    def test_actual_public_attempt_keeps_all_gates_closed(self):
        self.assertFalse(self.summary['completeClaim'])
        self.assertEqual(self.summary['publication'], 'BLOCKED')
        self.assertEqual(self.summary['liveC4'], 'NOT_EVALUATED')
        self.assertIn(self.summary['state'], ('REPORT_AVAILABLE', 'UNAVAILABLE'))
        if self.summary['state'] == 'UNAVAILABLE':
            self.assertEqual(self.summary['transportStatus'], 'DEPENDENCY_INTEGRITY_ERROR')
            self.assertEqual(self.summary['findings'], [])
            self.assertNotIn('domainReport', self.record['response'])

    def test_actual_domain_report_has_performer_copy_findings(self):
        if self.summary['state'] != 'REPORT_AVAILABLE':
            self.skipTest('Fresh domain evaluation blocked: ' + self.summary['error'])
        finding = next(row for row in self.summary['findings'] if row['id'] == 'AR_OPERATION_PERFORMER')
        # Copying a reported reference does not verify the person's identity.
        self.assertEqual(finding['disposition'], 'NOT_EVALUATED')
        self.assertEqual(finding['failedPrerequisites'], ['PERFORMER_IDENTITY'])
        self.assertEqual(finding['diagnostics'], [])
        self.assertCountEqual([row['predicateId'] for row in finding['comparisons']],
                              ['mapping.performedByPartyRef', 'body.performerRef'])
        for row in finding['comparisons']:
            self.assertTrue(row['sourcePresent'])
            self.assertTrue(row['destinationPresent'])
            self.assertTrue(row['equal'])
        identity = next(row for row in self.record['response']['domainReport']['dependencyFindings']
                        if row['id'] == 'PERFORMER_IDENTITY')
        self.assertEqual(identity['disposition'], 'NOT_EVALUATED')
        self.assertEqual(len(self.summary['findings']), 49)
        self.assertIsNone(self.summary['payload'])
        self.assertEqual(self.summary['runtimeAdmission'], 'NOT_ESTABLISHED')
        self.assertFalse(self.summary['completeClaim'])
        self.assertEqual(self.summary['liveC4'], 'NOT_EVALUATED')
        self.assertEqual(self.summary['publication'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
