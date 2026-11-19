"""Link fictional notes for draft review, without admitting or verifying them."""
from collections import Counter
import copy
import hashlib


def link_example_evidence(capture, catalog, job, seconds, issues):
    if capture['format'] != 'spray-draft.v5':
        return None
    result = {'selection': capture['exampleEvidenceSetId'], 'evidenceSet': None, 'source': None,
              'qualification': 'FICTIONAL_EXAMPLE_ONLY', 'evidenceUse': 'NOT_ADMITTED',
              'links': [{ 'conditionId': row['id'], 'phase': row['phase'], 'conditionStatus': 'NOT_EVALUATED',
                         'status': 'NO_EXAMPLE', 'record': None, 'source': None,
                         'message': 'No example note is linked to this condition.'}
                        for row in job['conditions']] if job else []}
    if not result['selection'] or not job:
        return result
    choices = catalog.get('exampleEvidenceSets', [])
    if type(choices) is not list:
        choices = []
    matches = [(i, row) for i, row in enumerate(choices) if type(row) is dict and row.get('id') == result['selection']]
    if len(matches) != 1:
        issues.append({'field': 'exampleEvidenceSetId', 'code': 'UNKNOWN_EXAMPLE_EVIDENCE', 'level': 'error',
                       'message': 'Choose the listed fictional notes, or choose no example evidence. The selected notes could not be found uniquely.'})
        return result
    index, selected = matches[0]
    pointer = '/exampleEvidenceSets/' + str(index)
    source = {'catalogRawSha256': capture['catalogSha256'], 'pointer': pointer}
    result.update(evidenceSet=copy.deepcopy(selected), source=source)
    context_keys = {'productId', 'parcelId', 'cropId', 'performerId', 'methodId', 'treatmentTargetId'}
    valid_set = (selected.get('format') == 'spray-example-condition-evidence.v1' and selected.get('fictional') is True
                 and type(selected.get('records')) is list and type(selected.get('reportedContext')) is dict
                 and set(selected['reportedContext']) == context_keys
                 and all(type(selected.get(k)) is str and selected[k] for k in ('id', 'revision', 'jobId', 'jobRevision', 'activityInstanceRef'))
                 and type(selected.get('event')) is dict and set(selected['event']) == {'start', 'end'})
    context_matches = False
    if valid_set:
        try:
            start, end = (seconds(capture['event'][key]) for key in ('start', 'end'))
            context_matches = (start <= end and all(seconds(selected['event'][key]) == seconds(capture['event'][key]) for key in ('start', 'end'))
                               and all(selected['reportedContext'][key] == capture[key] for key in context_keys)
                               and (selected['jobId'], selected['jobRevision'], selected['activityInstanceRef'])
                               == (job['id'], job['revision'], job['activityInstanceRef']))
        except (ValueError, TypeError):
            pass
    if not valid_set or not context_matches:
        message = ('The selected notes are not a supported fictional example.' if not valid_set else
                   'These fictional notes describe a different job, person, product, method, target or time. They were not linked.')
        for link in result['links']:
            link.update(status='INVALID_EXAMPLE' if not valid_set else 'CONTEXT_MISMATCH', message=message)
        issues.append({'field': 'exampleEvidenceSetId', 'code': 'EXAMPLE_EVIDENCE_NOT_LINKED', 'level': 'warning', 'message': message})
        return result
    records = selected['records']
    ids = Counter(row.get('id') for row in records if type(row) is dict and type(row.get('id')) is str)
    known_conditions = {row['id'] for row in job['conditions']}
    if any(type(row) is not dict or type(row.get('conditionId')) is not str or row['conditionId'] not in known_conditions for row in records):
        issues.append({'field': 'exampleEvidenceSetId', 'code': 'UNKNOWN_EXAMPLE_CONDITION', 'level': 'warning',
                       'message': 'A fictional note names an unknown condition and was not linked.'})
    for condition, link in zip(job['conditions'], result['links']):
        notes = [(i, row) for i, row in enumerate(records) if type(row) is dict and row.get('conditionId') == condition['id']]
        if not notes:
            continue
        valid_note = len(notes) == 1
        if valid_note:
            record_index, note = notes[0]
            valid_note = (note.get('fictional') is True and note.get('phase') == condition['phase']
                          and note.get('conditionMeaning') == condition['meaning']
                          and all(type(note.get(k)) is str and note[k] for k in ('id', 'revision', 'originalText', 'observedAt', 'supports', 'limitations'))
                          and ids[note['id']] == 1
                          and hashlib.sha256(note['originalText'].encode('utf-8')).hexdigest() == note.get('originalTextSha256'))
            if valid_note:
                try:
                    valid_note = start <= seconds(note['observedAt']) <= end
                except (ValueError, TypeError):
                    valid_note = False
        if not valid_note:
            link.update(status='INVALID_EXAMPLE', message='The fictional note is ambiguous, changed or does not match this exact condition and time.')
            issues.append({'field': 'exampleEvidence.' + condition['id'], 'code': 'INVALID_EXAMPLE_NOTE', 'level': 'warning', 'message': link['message']})
            continue
        link.update(status='EXAMPLE_LINKED', record=copy.deepcopy(note),
                    source={'catalogRawSha256': capture['catalogSha256'], 'pointer': pointer + '/records/' + str(record_index)},
                    message='Fictional note linked for review. The condition remains unverified.')
    return result
