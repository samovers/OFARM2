"""Reported liquid amount, exact originals and closed verification gates."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid

from app import DraftInbox, Problem
from draft import HERE, GATES, VALIDATOR, check_capture
from test_draft import DraftOnlyVerifier, raw
from test_spray_details import detailed_example
from verifier import Verifier, build_packet


def liquid_example(liquid='water', value='200.00'):
    capture = detailed_example()
    capture.update(format='spray-draft.v3', applicationVolume={
        'liquidId': liquid, 'value': value, 'unitId': 'litres-per-hectare'})
    return capture


class ApplicationVolumeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.inbox = DraftInbox(Path(self.directory.name) / 'drafts.sqlite3', verifier=DraftOnlyVerifier())

    def tearDown(self):
        self.directory.cleanup()

    def test_water_and_mixture_keep_decimal_choice_and_separate_product_dose(self):
        for liquid, label in [('water', 'Water only'), ('spray-mixture', 'Finished spray mixture')]:
            with self.subTest(liquid=liquid):
                capture = liquid_example(liquid)
                original = raw(capture)
                saved = self.inbox.save(original)
                self.assertEqual(saved['issues'], [])
                self.assertTrue(VALIDATOR.is_valid(saved['draftSource']))
                dose, volume = saved['draftSource']['actualQuantityParameters']
                self.assertEqual((dose['parameterRole'], dose['reportedValue']), ('DOSE', '0.30'))
                self.assertEqual((volume['parameterRole'], volume['value'], volume['reportedValue']),
                                 ('APPLICATION_VOLUME', 200.0, '200.00'))
                self.assertEqual(volume['unitRef'], 'scheme:ucum:L/har')
                self.assertEqual(volume['qualifier'], 'HUMAN_REPORTED')
                self.assertIn(label, volume['notes'])
                self.assertNotIn('materialRef', volume)
                self.assertNotIn('normalizedValue', volume)
                self.assertEqual(saved['displayLabels']['applicationLiquids']['label'], label)
                self.assertEqual(saved['displayLabels']['applicationVolumeUnits']['label'], 'L/ha')
                reviewed = self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': saved['originalSha256']}))
                self.assertEqual(reviewed['originalText'].encode(), original)
                self.assertEqual(self.inbox.read(capture['draftId'])['capture'], capture)
                self.assertEqual(reviewed['gates'], GATES)

    def test_v3_requires_exact_reported_fields_and_rejects_authority_flags(self):
        capture = liquid_example(); del capture['applicationVolume']
        with self.assertRaises(ValueError):
            self.inbox.save(raw(capture))
        for field in ('liquidId', 'value', 'unitId'):
            capture = liquid_example(); del capture['applicationVolume'][field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                self.inbox.save(raw(capture))
        for key, value in [('materialVerified', True), ('totalLitres', '200')]:
            capture = liquid_example(); capture['applicationVolume'][key] = value
            with self.subTest(extra=key), self.assertRaises(ValueError):
                self.inbox.save(raw(capture))
        capture = liquid_example(); capture['applicationVolume']['value'] = 200
        with self.assertRaises(ValueError):
            self.inbox.save(raw(capture))

    def test_invalid_amount_choice_or_unit_is_preserved_and_blocks_review(self):
        variants = [('value', v) for v in ['', '-1', '200,5', '1e2', 'NaN', 'Infinity',
                                            '9007199254740993', '200.00000000000000001']]
        variants += [('unitId', v) for v in ['', 'litres', 'kilograms-per-hectare']]
        variants += [('liquidId', v) for v in ['', 'unknown-liquid']]
        for field, value in variants:
            with self.subTest(field=field, value=value):
                capture = liquid_example(); capture['applicationVolume'][field] = value
                original = raw(capture); saved = self.inbox.save(original)
                self.assertEqual(saved['originalText'].encode(), original)
                self.assertIsNone(saved['draftSource'])
                self.assertFalse(saved['canAcknowledgeDraft'])
                self.assertTrue(any(row['field'] == 'applicationVolume.' + field for row in saved['issues']))
                with self.assertRaises(Problem):
                    self.inbox.acknowledge(capture['draftId'], raw({'originalSha256': saved['originalSha256']}))

    def test_zero_is_a_visible_reported_warning_without_inventing_a_use_rule(self):
        saved = self.inbox.save(raw(liquid_example(value='0.00')))
        self.assertTrue(saved['canAcknowledgeDraft'])
        self.assertTrue(any(row['code'] == 'ZERO_APPLICATION_VOLUME' and row['level'] == 'warning'
                            for row in saved['issues']))
        self.assertEqual(saved['draftSource']['actualQuantityParameters'][1]['reportedValue'], '0.00')
        self.assertEqual(saved['gates'], GATES)

    def test_v1_v2_originals_keep_their_catalog_and_do_not_acquire_an_amount(self):
        for path in ['fixtures/original/original.json',
                     'fixtures/details/original.json']:
            with self.subTest(path=path):
                original = (HERE / path).read_bytes()
                saved = self.inbox.save(original)
                self.assertEqual(saved['issues'], [])
                self.assertEqual(saved['originalText'].encode(), original)
                self.assertNotIn('applicationVolume', saved['capture'])
                self.assertEqual(len(saved['draftSource']['actualQuantityParameters']), 1)
                packet = build_packet(saved)
                self.assertNotIn('applicationVolume', packet['intent']['assertionBody']['proposition']['body']['parameters'])
                self.assertIn('water or mixture amount are missing', packet['missingInputs'][4]['message'])

    def test_correction_preserves_the_first_liquid_amount_and_original(self):
        first = liquid_example(); original = raw(first); self.inbox.save(original)
        second = copy.deepcopy(first); second['draftId'] = str(uuid.uuid4())
        second['applicationVolume'].update(liquidId='spray-mixture', value='250.50')
        saved = self.inbox.save(raw(second))
        self.assertEqual(self.inbox.read(first['draftId'])['originalText'].encode(), original)
        self.assertEqual(saved['capture']['applicationVolume'], second['applicationVolume'])
        self.assertEqual(saved['capture']['dose'], first['dose'])
        changed = copy.deepcopy(first); changed['applicationVolume']['value'] = '999'
        with self.assertRaises(Problem):
            self.inbox.save(raw(changed))

    def test_proposal_traces_amount_to_its_original_without_inventing_material_identity(self):
        checker = Verifier()
        for liquid in ('water', 'spray-mixture'):
            capture = liquid_example(liquid)
            draft = check_capture(raw(capture), (HERE / 'catalog.json').read_bytes(), '2026-11-18T19:00:00Z')
            before = copy.deepcopy(draft); packet = build_packet(draft)
            atom = packet['intent']['assertionBody']['proposition']['body']
            dose, volume = atom['quantityParameters']
            self.assertEqual(draft, before)
            self.assertEqual(packet['capture'], capture)
            self.assertEqual(volume['parameterRole'], 'APPLICATION_VOLUME')
            self.assertEqual(atom['parameters']['applicationVolume'], {'quantityParameterId': volume['parameterId']})
            self.assertEqual(volume['value']['quantity']['decimal'], capture['applicationVolume']['value'])
            self.assertEqual(volume['value']['original']['sourcePointer'], '/actualQuantityParameters/1/reportedValue')
            self.assertEqual(volume['value']['original']['sourceBinding']['ref'], draft['draftSource']['executionRecordPayloadId'])
            self.assertEqual(volume['value']['original']['lexicalValue'], '200.00')
            self.assertEqual(volume['applicationMaterialInterpretation'], 'UNRESOLVED_SOURCE_MATERIAL')
            self.assertEqual(volume['material']['presence'], 'UNREPORTED')
            self.assertEqual(volume['basis']['presence'], 'UNREPORTED')
            self.assertNotIn('binding', volume['material'])
            self.assertNotIn('components', volume['material'])
            self.assertNotIn('materialDefinition', volume['material'])
            self.assertNotIn('rate', atom['parameters'])
            self.assertEqual(dose['parameterRole'], 'DOSE')
            self.assertEqual(packet['proposedResult']['assertionBody'], packet['intent']['assertionBody'])
            self.assertIn('recorded as reported', packet['missingInputs'][4]['message'])
            changed = copy.deepcopy(draft); changed['capture']['applicationVolume']['value'] = '250'
            self.assertNotEqual(checker.identity(packet), checker.identity(build_packet(changed)))


class PublicApplicationVolumeTests(unittest.TestCase):
    def test_actual_public_report_preserves_amount_and_detects_changed_result(self):
        folder = Path(os.environ.get('SPRAY_VOLUME_TEST_EVIDENCE', HERE / '.local/test-evidence/application-volume/public'))
        folder.mkdir(parents=True, exist_ok=True)
        capture = liquid_example()
        draft = check_capture(raw(capture), (HERE / 'catalog.json').read_bytes(), '2026-11-18T19:00:00Z')
        checker = Verifier(); packet = build_packet(draft); record = checker.invoke(packet)
        (folder / 'actual-response.json').write_bytes(raw(record))
        summary = checker.summary(record); (folder / 'summary.json').write_bytes(raw(summary))
        self.assertEqual(summary['state'], 'REPORT_AVAILABLE', summary)
        finding = next(row for row in summary['findings'] if row['id'] == 'AR_BODY')
        self.assertTrue(next(row for row in finding['comparisons'] if row['predicateId'] == 'mapping.assertionBody')['equal'])
        self.assertIsNone(summary['payload'])
        self.assertFalse(summary['completeClaim'])
        self.assertEqual(summary['liveC4'], 'NOT_EVALUATED')
        self.assertEqual(summary['publication'], 'BLOCKED')
        changed = copy.deepcopy(packet)
        changed['proposedResult']['assertionBody']['proposition']['body']['quantityParameters'][1]['value']['quantity']['decimal'] = '201.00'
        response = checker.invoke(changed)
        (folder / 'actual-changed-volume-response.json').write_bytes(raw(response))
        report = response['response']['domainReport']
        finding = next(row for row in report['mappingFindings'] if row['id'] == 'AR_BODY')
        self.assertTrue(any(row['code'] == 'COPY_MISMATCH' and row.get('detail') == 'mapping.assertionBody'
                            for row in finding['diagnostics']))
        self.assertIsNone(report['payload'])
        self.assertEqual(report['atomicCommit'], 'NOT_EVALUATED')
        self.assertEqual(report['runtimeAdmission'], 'NOT_ESTABLISHED')


if __name__ == '__main__':
    unittest.main()
