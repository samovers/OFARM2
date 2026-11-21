"""Non-authoritative capture checks. No typed assertion, authority or C4 call."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from example_amounts import check_example_amounts
from example_evidence import link_example_evidence

sys.dont_write_bytecode = True
from dependencies import SOURCE_ROOTS, EXECUTION_SELECTION
HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / 'source-pins.json').read_bytes())['files']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned(name):
    pin = PINS[name]
    path = SOURCE_ROOTS[pin['root']] / pin['path']
    raw = path.read_bytes()
    if sha(raw) != pin['sha256']:
        raise RuntimeError('Selected source changed: ' + name)
    return path, raw


def load_module(name, pin):
    path, _ = pinned(pin)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Reuse the already pinned library set without installing or modifying it.
manifest_path, raw_manifest = pinned('library_manifest')
library_manifest = json.loads(raw_manifest)
library_root = Path(EXECUTION_SELECTION['libraries']['root'])
for entry in library_manifest['files']:
    if sha((library_root / entry['path']).read_bytes()) != entry['rawSha256']:
        raise RuntimeError('Selected validation library changed: ' + entry['path'])
sys.path.insert(0, str(library_root))
from jsonschema import Draft202012Validator, FormatChecker

BUILDER = load_module('spray_rehearsal_builder', 'spray_builder')
TIME = load_module('spray_rehearsal_time', 'time_parser')
FORMAT = FormatChecker()


@FORMAT.checks('date-time', raises=ValueError)
def timestamp_format(value):
    if not isinstance(value, str):
        return True
    TIME.foreign_instant(value)
    return True


SCHEMA = json.loads(pinned('execution_schema')[1])
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FORMAT)
EVIDENCE_VALIDATOR = Draft202012Validator(json.loads(pinned('evidence_schema')[1]), format_checker=FORMAT)
ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')
GATES = {'liveC4': 'NOT_EVALUATED', 'runtimeAdmission': 'NOT_ESTABLISHED',
         'publication': 'BLOCKED', 'payload': None, 'accepted': False}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def capture_shape(raw):
    value = strict_json(raw)
    expected = {'format', 'draftId', 'capturedAt', 'catalogSha256', 'productId',
                'parcelId', 'cropId', 'dose', 'event'}
    if type(value) is dict and value.get('format') in ('spray-draft.v2', 'spray-draft.v3', 'spray-draft.v4', 'spray-draft.v5'):
        expected |= {'performerId', 'methodId', 'treatmentTargetId'}
    if type(value) is dict and value.get('format') in ('spray-draft.v3', 'spray-draft.v4', 'spray-draft.v5'):
        expected.add('applicationVolume')
    if type(value) is dict and value.get('format') in ('spray-draft.v4', 'spray-draft.v5'):
        expected.add('jobId')
    if type(value) is dict and value.get('format') == 'spray-draft.v5':
        expected.add('exampleEvidenceSetId')
    if type(value) is not dict or set(value) != expected:
        raise ValueError('The draft has missing or unexpected fields.')
    if value['format'] not in ('spray-draft.v1', 'spray-draft.v2', 'spray-draft.v3', 'spray-draft.v4', 'spray-draft.v5') or not isinstance(value['draftId'], str) or not ID.fullmatch(value['draftId']):
        raise ValueError('Invalid draft format or ID.')
    for key in expected - {'dose', 'event', 'applicationVolume'}:
        if type(value[key]) is not str or len(value[key]) > 200:
            raise ValueError('Invalid draft field: ' + key)
    objects = [('dose', {'value', 'unitId'}),
               ('event', {'start', 'end', 'startLocal', 'endLocal', 'timeZone'})]
    if value['format'] in ('spray-draft.v3', 'spray-draft.v4', 'spray-draft.v5'):
        objects.append(('applicationVolume', {'liquidId', 'value', 'unitId'}))
    for key, fields in objects:
        if type(value[key]) is not dict or set(value[key]) != fields:
            raise ValueError('Invalid draft field: ' + key)
        if any(type(v) is not str or len(v) > 200 for v in value[key].values()):
            raise ValueError('Invalid draft value: ' + key)
    return value


def check_capture(raw, catalog_raw, received_at):
    capture = capture_shape(raw)
    catalog = strict_json(catalog_raw)
    issues, checks = [], []
    def issue(field, code, message, level='error'):
        issues.append({'field': field, 'code': code, 'message': message, 'level': level})
    def selected(group, key, label):
        match = next((row for row in catalog.get(group, []) if row['id'] == capture[key]), None)
        if match is None:
            issue(key, 'MISSING_OR_UNKNOWN_CHOICE', 'Choose ' + label + ' from the example list.')
        return match

    if capture['catalogSha256'] != sha(catalog_raw):
        issue('catalog', 'CATALOG_CHANGED', 'The saved list has changed. Make a new draft using the current list; this original is kept.')
    product = selected('products', 'productId', 'a product')
    parcel = selected('parcels', 'parcelId', 'a parcel')
    crop = selected('crops', 'cropId', 'a crop')
    job = (selected('jobs', 'jobId', 'an example job')
           if capture['format'] in ('spray-draft.v4', 'spray-draft.v5') and capture['catalogSha256'] == sha(catalog_raw) else None)
    performer, method, treatment_target = None, None, None
    if capture['format'] in ('spray-draft.v2', 'spray-draft.v3', 'spray-draft.v4', 'spray-draft.v5'):
        performer = selected('performers', 'performerId', 'the person who sprayed')
        method = selected('methods', 'methodId', 'the spraying method')
        treatment_target = selected('treatmentTargets', 'treatmentTargetId', 'the treatment target')
    if parcel and crop and parcel['cropId'] != crop['id']:
        issue('cropId', 'CROP_PARCEL_MISMATCH', 'This crop does not match the example parcel. Check the selection.')
    unit = next((row for row in catalog['units'] if row['id'] == capture['dose']['unitId']), None)
    if unit is None:
        issue('unitId', 'UNKNOWN_UNIT', 'Choose L/ha or kg/ha. The app will not guess a unit.')
    amount = None
    lexical = capture['dose']['value']
    if not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', lexical, re.ASCII):
        issue('dose', 'INVALID_DOSE', 'Enter a dose such as 0.3, using a dot. Negative amounts are not supported by this form.')
    else:
        decimal = Decimal(lexical)
        number = float(decimal)
        if not math.isfinite(number) or Decimal(str(number)) != decimal:
            issue('dose', 'DOSE_PRECISION_LOSS', 'This value cannot be copied exactly into the record. Keep the original and review its number format.')
        else:
            amount = number
            if decimal == 0:
                issue('dose', 'ZERO_DOSE', 'The dose is zero. Check that this is what you meant to record.', 'warning')

    liquid, volume_unit, volume_amount = None, None, None
    if capture['format'] in ('spray-draft.v3', 'spray-draft.v4', 'spray-draft.v5'):
        volume = capture['applicationVolume']
        liquid = next((row for row in catalog.get('applicationLiquids', []) if row['id'] == volume['liquidId']), None)
        if liquid is None:
            issue('applicationVolume.liquidId', 'MISSING_OR_UNKNOWN_LIQUID', 'Choose whether the amount is water only or finished spray mixture.')
        volume_unit = next((row for row in catalog['units'] if row['id'] == volume['unitId'] == 'litres-per-hectare'), None)
        if volume_unit is None:
            issue('applicationVolume.unitId', 'INVALID_VOLUME_UNIT', 'Record the water or mixture amount in L/ha. A tank total cannot be converted without its treated area.')
        volume_lexical = volume['value']
        if not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', volume_lexical, re.ASCII):
            issue('applicationVolume.value', 'INVALID_APPLICATION_VOLUME', 'Enter the water or mixture amount per hectare using a dot, for example 200. Do not enter a negative amount.')
        else:
            decimal = Decimal(volume_lexical)
            number = float(decimal)
            if not math.isfinite(number) or Decimal(str(number)) != decimal:
                issue('applicationVolume.value', 'VOLUME_PRECISION_LOSS', 'This amount cannot be copied exactly into the record. Keep the original and review its number format.')
            else:
                volume_amount = number
                if decimal == 0:
                    issue('applicationVolume.value', 'ZERO_APPLICATION_VOLUME', 'The water or mixture amount is zero. Check that this is what you meant to record.', 'warning')

    if job:
        # Compare recorded facts with a fictional plan; never replace actual
        # entries or turn matching entries into proof of work conditions.
        planned = job['planned']
        for key, label in [('productId', 'product'), ('parcelId', 'parcel'), ('cropId', 'crop'),
                           ('methodId', 'spraying method'), ('treatmentTargetId', 'treatment target')]:
            if capture[key] != planned[key]:
                issue('job.' + key, 'EXAMPLE_JOB_DIFFERENCE', 'The recorded ' + label + ' differs from the example job. Your entered value is kept.', 'warning')
        # Keep historical job-only comparisons for catalogs without separate
        # amount rules. New rules produce their own independent results below.
        for key, label in ([] if 'exampleAmountRules' in catalog else
                           [('dose', 'product dose'), ('applicationVolume', 'water or mixture amount')]):
            value, plan = capture[key], planned[key]
            same = value['unitId'] == plan['unitId']
            if key == 'applicationVolume':
                same = same and value['liquidId'] == plan['liquidId']
            if re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', value['value'], re.ASCII):
                same = same and Decimal(value['value']) == Decimal(plan['value'])
                if not same:
                    issue('job.' + key, 'EXAMPLE_JOB_DIFFERENCE', 'The recorded ' + label + ' differs from the example job. Your entered value is kept.', 'warning')

    amount_rule_checks = check_example_amounts(capture, catalog, job, sha(raw), issues)
    condition_evidence = link_example_evidence(capture, catalog, job, TIME.foreign_seconds, issues)

    times = {}
    for key, value, label in [('start', capture['event']['start'], 'application start'),
                              ('end', capture['event']['end'], 'application end'),
                              ('capturedAt', capture['capturedAt'], 'capture time')]:
        try:
            times[key] = TIME.foreign_seconds(value)
        except ValueError:
            issue(key, 'INVALID_TIME', 'Enter a valid ' + label + ' with a known time zone.')
    for key in ('start', 'end'):
        try:
            local = datetime.strptime(capture['event'][key + 'Local'], '%Y-%m-%dT%H:%M')
            zone = ZoneInfo(capture['event']['timeZone'])
            candidates = set()
            for fold in (0, 1):
                instant = local.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
                if instant.astimezone(zone).replace(tzinfo=None) == local:
                    candidates.add(instant)
            if len(candidates) != 1:
                issue(key, 'LOCAL_TIME_AMBIGUOUS_OR_MISSING', 'This clock time is skipped or repeated by a clock change. A precise offset is needed; this form cannot guess it.')
            elif key in times and TIME.foreign_seconds(next(iter(candidates)).isoformat()) != times[key]:
                issue(key, 'LOCAL_TIME_MISMATCH', 'The saved application time does not match the time entered on the form.')
        except (ValueError, ZoneInfoNotFoundError):
            issue(key, 'INVALID_LOCAL_TIME', 'Enter a valid local time in your device time zone.')
    if 'start' in times and 'end' in times and times['end'] < times['start']:
        issue('end', 'REVERSED_INTERVAL', 'The application end is before its start.')
    if 'end' in times and 'capturedAt' in times and times['end'] > times['capturedAt']:
        issue('end', 'APPLICATION_AFTER_CAPTURE', 'The application ends after this entry was captured. Check the time.', 'warning')
    # Receipt time comes from this local server, never from an input success flag.
    receipt_seconds = TIME.foreign_seconds(received_at)
    if 'capturedAt' in times and times['capturedAt'] > receipt_seconds:
        issue('capturedAt', 'DEVICE_CLOCK_AHEAD', 'Your device capture time is ahead of this computer. Review the clock.', 'warning')

    for label, fields in [
        ('Product, parcel and crop', {'productId', 'parcelId', 'cropId', 'catalog'}),
        ('Dose and unit', {'dose', 'unitId'}),
        ('Application and capture times', {'start', 'end', 'capturedAt'})]:
        found = [item for item in issues if item['field'] in fields]
        checks.append({'label': label, 'status': 'ERROR' if any(v['level'] == 'error' for v in found)
                       else 'REVIEW' if found else 'CHECKED'})
    if capture['format'] in ('spray-draft.v2', 'spray-draft.v3', 'spray-draft.v4', 'spray-draft.v5'):
        details_error = any(item['field'] in {'performerId', 'methodId', 'treatmentTargetId'} for item in issues)
        checks.append({'label': 'Person, spraying method and treatment target', 'status': 'ERROR' if details_error else 'CHECKED'})
    if capture['format'] in ('spray-draft.v3', 'spray-draft.v4', 'spray-draft.v5'):
        volume_issues = [item for item in issues if item['field'].startswith('applicationVolume.')]
        checks.append({'label': 'Water or mixture amount',
                       'status': 'ERROR' if any(item['level'] == 'error' for item in volume_issues)
                       else 'REVIEW' if volume_issues else 'CHECKED'})
    if capture['format'] in ('spray-draft.v4', 'spray-draft.v5'):
        job_issues = [item for item in issues if item['field'] == 'jobId' or item['field'].startswith('job.')]
        checks.append({'label': 'Example job selection and recorded details',
                       'status': 'ERROR' if any(item['level'] == 'error' for item in job_issues)
                       else 'REVIEW' if job_issues else 'CHECKED'})

    source, evidence = None, None
    if not any(item['level'] == 'error' for item in issues):
        refs = BUILDER.DemoPayloadRefs(farm=catalog['farm']['id'], field=parcel['id'],
            cycle=parcel['cycleId'], farmer=catalog['farmer']['id'], sprayer=catalog['equipmentId'],
            applied_resource='resource:fictional-draft-only', product_binding=product['id'],
            crop_binding=crop['id'], photo_evidence='unused:no-photo', onboarding_evidence='unused:no-admission',
            code_binding_profile_ref='profile:fictional-draft-only')
        # This descriptor identifies the captured entry itself. It supplies no
        # independent evidence that the application occurred and admits no use.
        evidence = {'schemaVersion': 'ofarm.evidencerecord.v0.1',
            'evidenceRecordId': 'draft-evidence:' + capture['draftId'],
            'evidenceClass': 'OTHER', 'capturedAt': capture['capturedAt'],
            'recordedAt': received_at, 'capturedByPartyRef': catalog['farmer']['id'],
            'rawAssetRef': 'draft-capture:' + capture['draftId'], 'rawAssetDigest': 'sha256:' + sha(raw),
            'mediaType': 'application/json', 'evidenceState': 'CAPTURED',
            'interpretation': {'interpretationClass': 'NONE'},
            'notes': 'Fictional draft capture only. No independent corroboration or admitted source use.'}
        source = BUILDER.spray_payload(erp_id='draft-source:' + capture['draftId'], refs=refs,
            actor_ref=catalog['farmer']['id'], event_start=capture['event']['start'],
            event_end=capture['event']['end'], dose_value=amount, unit_ref=unit['ref'], evidence_refs=[evidence['evidenceRecordId']])
        source['capturedAt'] = capture['capturedAt']
        source['actualAction']['actionLabel'] = 'Crop-protection application — unverified draft'
        if performer:
            # The recorder remains actorPartyRef. The explicit reported
            # physical operator is a separate field; no role proof is implied.
            source['actor']['operatorPartyRef'] = performer['id']
        if method:
            source['actualAction']['methodRef'] = method['id']
        if job:
            source['actualAction']['notes'] = ('Selected fictional job ' + job['id'] + ' revision ' + job['revision']
                + ' from catalog sha256:' + capture['catalogSha256'] + '. Job conditions have not been verified.')
        # The existing execution schema has no explicit target-organism slot.
        # Keep that value in the captured original, never in an invented field.
        quantity = source['actualQuantityParameters'][0]
        quantity.update(quantityKindRef=unit['quantityKindRef'], reportedValue=lexical, reportedUnitLabel=unit['label'])
        if liquid:
            # This choice reports a category, not an immutable material identity
            # or mixture recipe. Preserve it without inventing either binding.
            source['actualQuantityParameters'].append({
                'parameterRole': 'APPLICATION_VOLUME',
                'quantityKindRef': volume_unit['quantityKindRef'], 'unitRef': volume_unit['ref'],
                'value': volume_amount, 'reportedValue': volume_lexical,
                'reportedUnitLabel': volume_unit['label'], 'qualifier': 'HUMAN_REPORTED',
                'notes': 'Reported as ' + liquid['label'] + '; choice retained at /applicationVolume/liquidId in the original capture. Exact material identity and mixture composition are not established.'})
        source['sourcePayload'].update(sourceSystemRef='app:spray-draft-rehearsal',
            sourcePayloadRef='draft-capture:' + capture['draftId'], sourcePayloadHash='sha256:' + sha(raw))
        schema_errors = list(VALIDATOR.iter_errors(source)) + list(EVIDENCE_VALIDATOR.iter_errors(evidence))
        for error in schema_errors:
            issue('record', 'SOURCE_SCHEMA_INVALID', 'The draft could not be mapped to the existing record format: ' + error.message)
        checks.append({'label': 'Existing spray record format', 'status': 'ERROR' if schema_errors else 'CHECKED'})
        if schema_errors:
            source, evidence = None, None
    else:
        checks.append({'label': 'Existing spray record format', 'status': 'NOT_CHECKED'})

    checks.append({'label': 'Original entry retained', 'status': 'CHECKED'})
    display_labels = {group: {'id': row['id'], 'label': row['label']} for group, row in [
        ('products', product), ('parcels', parcel), ('crops', crop), ('units', unit),
        ('performers', performer), ('methods', method), ('treatmentTargets', treatment_target),
        ('applicationLiquids', liquid), ('applicationVolumeUnits', volume_unit), ('jobs', job)] if row}
    return {'capture': capture, 'originalSha256': sha(raw), 'receivedAt': received_at,
            'displayLabels': display_labels,
            'draftJob': job,
            'jobSource': {'catalogRawSha256': capture['catalogSha256'], 'pointer': '/jobs/' + str(catalog['jobs'].index(job))} if job else None,
            'jobConditions': [{**condition, 'status': 'NOT_EVALUATED'} for condition in job['conditions']] if job else [],
            'exampleAmountChecks': amount_rule_checks,
            'exampleConditionEvidence': condition_evidence,
            'issues': issues, 'checks': checks, 'draftSource': source, 'draftEvidence': evidence,
            'canAcknowledgeDraft': not any(item['level'] == 'error' for item in issues),
            'gates': dict(GATES),
            'unresolved': [
                'The farm and product list are examples. They are not real farm evidence.',
                'Dose limits and permission to use the product have not been checked.',
                ('The named person, method and treatment target are reported examples. Their identities, meanings and use are not independently verified.'
                 if capture['format'] in ('spray-draft.v2', 'spray-draft.v3', 'spray-draft.v4', 'spray-draft.v5') else
                 'This older draft does not record who sprayed, the spraying method or the treatment target.'),
                ('The water or mixture amount is recorded as reported. Its exact material identity, basis and source evidence still need verification.'
                 if liquid else 'The water or mixture amount is not recorded in this draft.'),
                ('The versioned example job is linked. Its conditions are unverified; adopted work rules and eligible evidence are still missing.'
                 if job else 'The full checker still needs the specific work record and its conditions.'),
                ('The separate example amount checks do not establish the real rules for interpreting dose, materials or treated area.'
                 if amount_rule_checks else 'The agreed meaning of dose versus rate still needs a separate rule.'),
                'Real approval also needs agreed rules and original records from a trusted source.'
            ],
            'typedClaim': None, 'c3Completion': 'NOT_CLAIMED'}
