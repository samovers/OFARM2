"""Two local fictional comparisons; no policy adoption or quantity conversion."""
import copy
from decimal import Decimal
import re


def decimal_text(value):
    return type(value) is str and len(value) <= 200 and re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', value, re.ASCII)


def check_example_amounts(capture, catalog, job, original_sha, issues):
    if not job or 'exampleAmountRules' not in catalog:
        return []
    definitions = catalog['exampleAmountRules']
    results = []
    for key, role, field, material, material_pointer, label, error_fields in [
        ('product', 'PRODUCT_DOSE', 'dose', capture['productId'], '/productId', 'Product amount', {'dose', 'unitId', 'productId'}),
        ('water', 'WATER_AMOUNT', 'applicationVolume', capture['applicationVolume']['liquidId'],
         '/applicationVolume/liquidId', 'Water amount', {'applicationVolume.value', 'applicationVolume.unitId', 'applicationVolume.liquidId'})]:
        rule = definitions.get(key) if type(definitions) is dict else None
        value = capture[field]
        result = {'role': role, 'label': label, 'rule': copy.deepcopy(rule),
                  'ruleSource': {'catalogRawSha256': capture['catalogSha256'], 'pointer': '/exampleAmountRules/' + key},
                  'originalSource': {'rawSha256': original_sha, 'amountPointer': '/' + field, 'materialPointer': material_pointer},
                  'observed': copy.deepcopy(value), 'materialId': material,
                  'status': 'NOT_CHECKED', 'message': 'The example rule is missing or unsupported.'}
        expected = rule.get('expected') if type(rule) is dict else None
        valid_rule = (type(rule) is dict and rule.get('format') == 'spray-example-amount-rule.v1'
                      and rule.get('fictional') is True and rule.get('role') == role
                      and rule.get('comparison') == 'EXACT_DECIMAL_SAME_UNIT'
                      and all(type(rule.get(k)) is str and rule[k] for k in ('id', 'revision', 'jobId', 'jobRevision', 'materialId'))
                      and type(expected) is dict and decimal_text(expected.get('value'))
                      and all(type(expected.get(k)) is str and expected[k] for k in ('unitId', 'unitRef', 'quantityKindRef')))
        invalid_entry = any(row['level'] == 'error' and row['field'] in error_fields for row in issues)
        unit = next((row for row in catalog['units'] if row['id'] == value['unitId']), None)
        if valid_rule:
            if (rule['jobId'], rule['jobRevision']) != (job['id'], job['revision']):
                result['message'] = 'This rule belongs to a different example job or version.'
            elif material != rule['materialId']:
                result['message'] = ('This rule checks Example product A only. The selected product is kept.' if key == 'product'
                                     else 'This rule checks water only. A finished mixture is not treated as water.')
            elif invalid_entry or not decimal_text(value['value']):
                result['message'] = 'Fix the entered amount, material choice or unit before this example check can run.'
            elif (not unit or value['unitId'] != expected['unitId']
                  or unit['ref'] != expected['unitRef'] or unit['quantityKindRef'] != expected['quantityKindRef']):
                result['message'] = 'The unit does not match this example rule. No conversion was made.'
            elif Decimal(value['value']) == Decimal(expected['value']):
                result.update(status='MATCH', message='The entered amount matches this example rule. This is not approval or proof of use.')
            else:
                result.update(status='DIFFERENT', message='The entered amount differs from this example rule. Your entered value is kept for review.')
        if result['status'] != 'MATCH' and not invalid_entry:
            issues.append({'field': 'amountRules.' + key,
                           'code': 'EXAMPLE_AMOUNT_DIFFERENCE' if result['status'] == 'DIFFERENT' else 'EXAMPLE_AMOUNT_NOT_CHECKED',
                           'message': label + ': ' + result['message'], 'level': 'warning'})
        results.append(result)
    return results
