"""Actual #47 transport for incomplete draft diagnostics, never admission."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path

from draft import HERE, PINS, SCHEMA, utc_now
from dependencies import VERIFIER_ROOT, TRANSPORT
import rfc8785

ACTION = 'ASSERT_OPERATION_CLAIM'
SELECTION_PATH = HERE / 'verifier-selection.json'
MISSING = [
    {'field': 'assertionActPosture / assertedAt', 'message': 'A trusted submission record and its time are missing. The device capture time is not a substitute.'},
    {'field': 'resources / subject', 'message': 'The field, farm and product still need their exact identity records and permission checks.'},
    {'field': 'performedByPartyRef / performedByBinding', 'message': 'Who physically did the spraying is not established by who entered the draft.'},
    {'field': 'workSpecification / parameters.method / parameters.targetOrganism', 'message': 'The chosen work, spraying method and treatment target are missing.'},
    {'field': 'parameters.rate / parameters.applicationVolume', 'message': 'An agreed dose-to-rate meaning and the water or mixture amount are missing. The entered dose is kept unchanged.'},
    {'field': 'evaluationSelection / source-use / protected state', 'message': 'Approved source-use rules and trusted transaction originals have not been supplied.'},
]


def missing_inputs(draft):
    missing = copy.deepcopy(MISSING)
    capture = draft['capture']
    if capture.get('performerId'):
        missing[2]['message'] = 'The person who sprayed is recorded as reported. Their exact identity and physical role still need verification.'
    if capture.get('methodId') and capture.get('treatmentTargetId'):
        missing[3]['message'] = 'The spraying method and treatment target are recorded. Their versioned definitions and the specific work record, including its conditions, are still missing.'
    if capture.get('applicationVolume'):
        missing[4]['message'] = 'The water or mixture amount per hectare is recorded as reported. Its exact material identity, basis and source evidence still need verification, and the agreed dose-to-rate meaning is still missing.'
    if draft.get('draftJob'):
        missing[3]['message'] = 'The versioned example job and its conditions are linked. The conditions have not been verified; adopted work, method and target rules and eligible evidence are still missing.'
    if draft.get('exampleAmountChecks'):
        missing[4]['message'] = 'Separate example rules check product and water amounts. Real approval still needs agreed rules for interpreting dose, verified materials and treated area, and evidence of the amounts actually used.'
    if any(row['status'] == 'EXAMPLE_LINKED' for row in (draft.get('exampleConditionEvidence') or {}).get('links', [])):
        missing[3]['message'] = 'Fictional notes are linked to job conditions for review. They do not prove spraying happened or that every treatment segment was finished. Real evidence and approved work rules are still missing.'
    return missing


def raw(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def binding(ref, value):
    return {'ref': ref, 'digest': 'sha256:' + sha(rfc8785.dumps(value))}


def build_packet(draft):
    """Map supported source fields; omit facts the capture does not establish.

    This is deliberately not a schema-valid completed O01 claim. The verifier
    owns the actual rejection/findings; no false selectors fill the gaps.
    """
    source, evidence = draft['draftSource'], draft['draftEvidence']
    if source is None or evidence is None:
        raise ValueError('Fix the entry errors before asking the verifier to check its proposed record.')
    source_binding = binding(source['executionRecordPayloadId'], source)
    declared_source = {**source_binding, 'schemaRef': SCHEMA['$id'],
                       'schemaVersion': source['schemaVersion'],
                       'schemaDigest': 'sha256:' + PINS['execution_schema']['sha256']}
    evidence_binding = binding(evidence['evidenceRecordId'], evidence)
    subject = {'subjectPosture': 'EXISTING_SUBJECT', **copy.deepcopy(source['subject'])}
    time = {'profile': 'PERFORMED_INTERVAL', **{key: source['effectiveTimeInterval'][key] for key in ('start', 'end')}}
    target = {'kind': source['executionExtent']['targetScope']['scopeType'],
              'binding': {'ref': source['executionExtent']['targetScope']['scopeRef']}}
    extent = {'posture': 'FULL_TARGET_SCOPE'}
    q = source['actualQuantityParameters'][0]
    quantity = {'parameterId': 'draft:entered-dose', 'parameterRole': q['parameterRole'],
        'valuePosture': 'ACTUAL',
        'material': {'presence': 'PRESENT', 'materialRole': q['materialRole'], 'binding': {'ref': q['materialRef']}},
        'value': {'state': 'STATED',
            'quantity': {'quantityKind': q['quantityKindRef'], 'unit': q['unitRef'], 'decimal': q['reportedValue']},
            'qualifier': q['qualifier'],
            'original': {'presence': 'PRESENT', 'lexicalValue': q['reportedValue'], 'unitText': q['reportedUnitLabel'],
                         'sourceBinding': source_binding, 'sourcePointer': '/actualQuantityParameters/0/reportedValue'}},
        'appliesTo': {'target': target, 'extent': extent, 'subjectTime': time}}
    proposition = {'form': 'ATOM', 'atomId': 'draft:spray',
        'definition': 'candidate:assertion-domain-construction:2026-10-21:r2:O01',
        'scope': {'subject': subject, 'subjectTime': time, 'extent': extent},
        'body': {'activity': source['actualAction']['actionType'],
                 'interventionKind': source['actualAction']['interventionKind'],
                 'claimPosture': 'PERFORMED', 'performanceFacet': 'OCCURRENCE',
                 'target': target, 'extent': extent,
                 'parameters': {'product': {'ref': q['materialRef']}},
                 'quantityParameters': [quantity]}}
    if draft['capture'].get('applicationVolume'):
        volume = source['actualQuantityParameters'][1]
        volume_id = 'draft:entered-application-volume'
        proposition['body']['quantityParameters'].append({
            'parameterId': volume_id, 'parameterRole': volume['parameterRole'],
            'valuePosture': 'ACTUAL',
            'applicationMaterialInterpretation': 'UNRESOLVED_SOURCE_MATERIAL',
            'material': {'presence': 'UNREPORTED', 'reason': volume['notes']},
            'basis': {'presence': 'UNREPORTED', 'reason': 'Per-hectare unit reported; exact basis identity and source interpretation not supplied.'},
            'value': {'state': 'STATED',
                'quantity': {'quantityKind': volume['quantityKindRef'], 'unit': volume['unitRef'], 'decimal': volume['reportedValue']},
                'qualifier': volume['qualifier'],
                'original': {'presence': 'PRESENT', 'lexicalValue': volume['reportedValue'],
                    'unitText': volume['reportedUnitLabel'], 'sourceBinding': source_binding,
                    'sourcePointer': '/actualQuantityParameters/1/reportedValue'}},
            'appliesTo': copy.deepcopy(quantity['appliesTo'])})
        proposition['body']['parameters']['applicationVolume'] = {'quantityParameterId': volume_id}
    body = {'assertionPosture': 'INITIAL', 'claimLanguageRevision': 'ofarm.complete-typed-claims.v0.1',
            'proposition': proposition, 'temporalBasis': {'sourceKind': 'BODY_TIME', 'time': time},
            'executionRecordPayloadBindings': [declared_source]}
    performer_ref = source['actor'].get('operatorPartyRef')
    if performer_ref is not None:
        proposition['body']['performedBy'] = {'ref': performer_ref}
        body['performedByBinding'] = {'ref': performer_ref}
    method_ref = source['actualAction'].get('methodRef')
    if method_ref is not None:
        proposition['body']['parameters']['method'] = {'ref': method_ref}
    # This role is explicit in the original capture. The execution carrier
    # does not supply a target-organism field, and none is fabricated for it.
    if draft['capture'].get('treatmentTargetId'):
        proposition['body']['parameters']['targetOrganism'] = {'ref': draft['capture']['treatmentTargetId']}
    job = draft.get('draftJob')
    if job:
        # These digests identify the exact local fictional definitions. They
        # supply no identity authority, source-use admission or condition proof.
        activity = {'ref': job['activityInstanceRef']}
        proposition['body']['activityInstance'] = activity
        proposition['body']['workSpecification'] = {
            'binding': binding(job['id'], job),
            'activityInstance': copy.deepcopy(activity),
            'procedure': binding(job['procedure']['id'], job['procedure']),
            'target': copy.deepcopy(job['target']), 'extent': copy.deepcopy(job['extent']),
            'startConditionIds': [row['id'] for row in job['conditions'] if row['phase'] == 'START'],
            'inProgressConditionIds': [row['id'] for row in job['conditions'] if row['phase'] == 'IN_PROGRESS'],
            'finishConditionIds': [row['id'] for row in job['conditions'] if row['phase'] == 'FINISH']}
        for parameter in proposition['body']['quantityParameters']:
            parameter['activityInstance'] = copy.deepcopy(activity)
    identifier = 'draft-assertion:' + draft['capture']['draftId']
    requested_scope = copy.deepcopy(source['executionExtent']['targetScope'])
    intent = {'schemaVersion': 'ofarm.operationassertioneffectintent.typed.v0.1',
              'resources': [{'resourceRole': 'TARGET_SCOPE', 'resourcePosture': 'AUTHORITY_TARGET',
                             'targetType': 'SCOPE', 'scope': requested_scope}],
              'effectSubject': {'subjectKind': 'OPERATION_ASSERTION', 'subjectRef': identifier,
                                'existencePosture': 'PROSPECTIVE_TARGET_ALLOWED'},
              'subject': subject, 'subjectTime': time, 'claimPosture': 'PERFORMED',
              'assertionBody': body, 'evidenceBindings': [source_binding, evidence_binding]}
    result = {'schemaVersion': 'ofarm.assertionrecord.typed.v0.1',
              'assertionRecordId': identifier, 'assertionType': 'OPERATION_CLAIM_ASSERTION',
              'anchorScopes': [copy.deepcopy(requested_scope)],
              'subject': copy.deepcopy(subject), 'subjectTime': copy.deepcopy(time),
              'assertionBody': copy.deepcopy(body), 'evidenceBindings': copy.deepcopy(intent['evidenceBindings']),
              'operationClaimContext': {'claimPosture': 'PERFORMED'}, 'claimState': 'PENDING_REVIEW'}
    if performer_ref is not None:
        intent['performedByPartyRef'] = performer_ref
        result['operationClaimContext']['performedByPartyRef'] = performer_ref
    packet = {'intent': intent, 'proposedResult': result,
            'capture': copy.deepcopy(draft['capture']),
            'draftSource': copy.deepcopy(source), 'draftEvidence': copy.deepcopy(evidence),
            'captureOriginalSha256': draft['originalSha256'],
            'qualification': 'INCOMPLETE_PROPOSAL_FROM_CAPTURED_FACTS_ONLY',
            'missingInputs': missing_inputs(draft),
            'sourceQualification': 'The source descriptors are retained locally. No independent evaluation selection or eligible-use evidence is invented or supplied.'}
    if job:
        packet.update(draftJob=copy.deepcopy(job), jobSource=copy.deepcopy(draft['jobSource']),
                      jobConditions=copy.deepcopy(draft['jobConditions']))
    if draft.get('exampleAmountChecks'):
        # Local example results remain diagnostic attachments. They are not
        # adopted source-use rules or owner inputs to the public verifier.
        packet['exampleAmountChecks'] = copy.deepcopy(draft['exampleAmountChecks'])
    if draft.get('exampleConditionEvidence') is not None:
        # Keep fictional notes outside governed evidence bindings and owner
        # inputs. Linking a demonstration source never satisfies a condition.
        packet['exampleConditionEvidence'] = copy.deepcopy(draft['exampleConditionEvidence'])
    return packet


class Verifier:
    def __init__(self):
        self.selection_raw = SELECTION_PATH.read_bytes()
        self.selection = json.loads(self.selection_raw)
        self.root = VERIFIER_ROOT
        self.seal = self.selection['manifestRawSha256']
        self.adapter_sha = sha(Path(__file__).read_bytes())
        path = self.root / 'owner_calls.py'
        if sha(path.read_bytes()) != self.selection['ownerTransportSha256']:
            raise ValueError('The selected verifier transport has changed.')
        self.transport = TRANSPORT
        self.transport.candidate_closure(self.seal)
        self.duty_ids = [row['id'] for row in json.loads((self.root / 'outer/source-duties.json').read_bytes())['duties']]
        self.lock = threading.Lock()

    def check(self, draft, directory):
        if draft['draftSource'] is None:
            return {'state': 'NOT_RUN', 'message': 'Fix the entry details first. The existing verifier has not run.',
                    'completeClaim': False, 'liveC4': 'NOT_EVALUATED', 'publication': 'BLOCKED', 'findings': []}
        packet = build_packet(draft)
        directory = Path(directory)
        cache = directory / (self.identity(packet) + '.json')
        with self.lock:
            try:
                if cache.exists():
                    record = json.loads(cache.read_bytes())
                    self.validate(record, packet)
                    return {**self.summary(record), 'fromCache': True}
                record = self.invoke(packet)
                directory.mkdir(parents=True, exist_ok=True)
                # Save exact transport output for inspection. Cache only an
                # actual domain report; an unavailable worker can be retried.
                with tempfile.NamedTemporaryFile(mode='wb', dir=directory, prefix='attempt-', suffix='.json', delete=False) as output:
                    output.write(raw(record)); output.flush(); os.fsync(output.fileno())
                    temporary = Path(output.name)
                if record['response'].get('status') == 'DOMAIN_REPORT':
                    os.replace(temporary, cache)
                return {**self.summary(record), 'fromCache': False}
            except (ValueError, KeyError, TypeError, OSError) as exc:
                return {'state': 'UNAVAILABLE', 'message': 'The verifier result could not be checked or saved safely. The draft is kept.',
                        'error': str(exc), 'completeClaim': False, 'liveC4': 'NOT_EVALUATED',
                        'publication': 'BLOCKED', 'findings': []}

    def identity(self, packet):
        return sha(raw({'packet': packet, 'verifierManifest': self.seal,
                        'adapterSha256': self.adapter_sha, 'selectionSha256': sha(self.selection_raw)}))

    def invoke(self, packet):
        # Use the existing public API and all of its execution/import guards.
        intent_bytes, result_bytes = raw(packet['intent']), raw(packet['proposedResult'])
        response = self.transport.evaluate_domain(intent_bytes, result_bytes,
            package={'root': str(self.root), 'manifestRawSha256': self.seal, 'selectedAction': ACTION},
            owner_inputs={})
        record = {'checkedAtUtc': utc_now(), 'checkId': self.identity(packet),
                  'verifierManifestRawSha256': self.seal, 'adapterSha256': self.adapter_sha,
                  'packet': packet, 'response': response}
        self.validate(record, packet)
        return record

    def validate(self, record, packet):
        if (record.get('checkId') != self.identity(packet) or record.get('packet') != packet
                or record.get('verifierManifestRawSha256') != self.seal
                or record.get('adapterSha256') != self.adapter_sha):
            raise ValueError('The saved verifier response belongs to different inputs or code.')
        response = record['response']
        if response.get('status') != 'DOMAIN_REPORT':
            # Real transport failures are retained, never turned into a report.
            if response.get('domainReport') is not None:
                raise ValueError('A failed verifier call supplied an unexpected report.')
            return
        report = response['domainReport']
        if (report.get('packageManifestRawSha256') != self.seal
                or report.get('implementationCompleteness') != 'INCOMPLETE'
                or report.get('runtimeAdmission') != 'NOT_ESTABLISHED'
                or report.get('atomicCommit') != 'NOT_EVALUATED'
                or report.get('payload') is not None or 'payloadDigest' in report
                or report.get('status') not in ('FAIL', 'DEPENDENCY_UNAVAILABLE', 'INPUT_ERROR')):
            raise ValueError('The verifier response exceeds this draft-only boundary.')
        findings = report.get('mappingFindings', []) + report.get('postconditionFindings', [])
        if [finding['id'] for finding in findings] != self.duty_ids:
            raise ValueError('The verifier did not return its complete ordered set of 49 findings.')
        for role, value in [('effectIntent', packet['intent']), ('proposedResult', packet['proposedResult'])]:
            expected = {'rawSha256': sha(raw(value)), 'valueDigest': 'sha256:' + sha(rfc8785.dumps(value))}
            if report.get('inputBindings', {}).get(role) != expected:
                raise ValueError('The verifier did not report the exact proposed inputs: ' + role)
        transport = response.get('transport', {})
        expected_request = {'kind': 'domain', 'operation': 'evaluate',
            'intentBytes': self.transport.encode(raw(packet['intent'])),
            'resultBytes': self.transport.encode(raw(packet['proposedResult'])),
            'package': {'root': str(self.root), 'manifestRawSha256': self.seal, 'selectedAction': ACTION},
            'ownerInputs': {}}
        request_bytes = self.transport.wire_bytes(expected_request)
        if (transport.get('requestRawSha256') != sha(request_bytes)
                or transport.get('requestByteLength') != len(request_bytes) or transport.get('returnCode') != 0):
            raise ValueError('The verifier transport does not match this request.')
        stdout = transport.get('stdout', {})
        output = base64.b64decode(stdout.get('originalBytesBase64', ''), validate=True)
        if sha(output) != stdout.get('rawSha256') or len(output) != stdout.get('byteLength'):
            raise ValueError('The saved verifier output bytes do not match their digest.')
        parsed = json.loads(output)
        if parsed != {key: value for key, value in response.items() if key != 'transport'}:
            raise ValueError('The displayed report differs from the actual worker output.')

    def summary(self, record):
        response = record['response']
        result = {'checkId': record['checkId'], 'checkedAtUtc': record['checkedAtUtc'],
                  'verifierManifestRawSha256': self.seal,
                  'missingInputs': copy.deepcopy(record['packet']['missingInputs']),
                  'completeClaim': False, 'liveC4': 'NOT_EVALUATED', 'publication': 'BLOCKED'}
        if response.get('status') != 'DOMAIN_REPORT':
            message = ('The verifier could not run because one of its required files no longer matches its recorded version. Your draft is saved.'
                       if response.get('status') == 'DEPENDENCY_INTEGRITY_ERROR' else
                       'The existing verifier could not run. Your draft is kept; nothing is approved.')
            return {**result, 'state': 'UNAVAILABLE', 'transportStatus': response.get('status'),
                    'message': message,
                    'error': response.get('error', 'Verifier execution unavailable.'), 'findings': []}
        report = response['domainReport']
        findings = report['mappingFindings'] + report['postconditionFindings']
        return {**result, 'state': 'REPORT_AVAILABLE', 'transportStatus': 'DOMAIN_REPORT',
                'reportStatus': report['status'],
                'message': 'The existing verifier ran. This proposal is incomplete; its missing inputs remain open.',
                'counts': {name: sum(item['disposition'] == name for item in findings) for name in ('PASS', 'FAIL', 'NOT_EVALUATED', 'NOT_APPLICABLE')},
                'findings': findings, 'schemaFindings': report.get('schemaFindings', {}),
                'errors': report.get('errors', []), 'inputBindings': report['inputBindings'],
                'payload': report['payload'], 'atomicCommit': report['atomicCommit'],
                'runtimeAdmission': report['runtimeAdmission'], 'implementationCompleteness': report['implementationCompleteness']}
