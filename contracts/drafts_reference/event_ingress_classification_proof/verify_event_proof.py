"""Non-default Event Ingress owner proof verification, offline and deterministic.

Public API: verify(..., trusted_pins=..., expected_proof_binding=..., use_mode=...).
The expected pins and proof selector must be selected independently of proof input.
This evaluates a concrete candidate contract; it never admits a runtime record.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from datetime import datetime
from pathlib import Path
from importlib.metadata import version,PackageNotFoundError
import report_contract
from report_contract import REPORT_SCHEMA

PACKAGE=Path(__file__).resolve().parent
CID='ofarm.event-ingress.pre-verdict-classification.v0.1'
ROLE='EVENT_INGRESS_CLASSIFICATION'
MILESTONE='CLASSIFICATION_COMPLETE_BEFORE_DEPENDENT_VERDICT'
REUSE='EXACT_ENVELOPE_REQUEST_PROFILE_CONTEXT_AND_PROOF'
RULES=['PACKAGE_PINS','STRICT_JSON','EXACT_SCHEMA_CLOSURE','INDEPENDENT_CONTEXT_PIN','INDEPENDENT_PROFILE_PIN','EXACT_PROOF_SELECTOR','WHOLE_INPUT_DIGESTS','EXACT_SOURCE_BYTES','CONTRACT_BINDINGS','OWNER_CONTEXT','REQUEST_CONTEXT','UNIQUE_CASE_SELECTION','INDEPENDENT_CLASSIFICATION','COMPLETE_DOMINANT_CONTEXT','FAMILY_EQUALITY','COMMIT_CLASS_EQUALITY','PRE_VERDICT_INPUT_CLOSURE','EXACT_REUSE']
INPUT_ROLES=['PINNED_CONTRACT','SELECTED_CLASSIFICATION_PROFILE','FIXED_ENVELOPE','FIXED_INGRESS_REQUEST','INDEPENDENT_OWNER_CONTEXT']
SCHEMA_PATHS={'contract':'schemas/contract.schema.json','proof':'schemas/proof.schema.json','context':'schemas/context.schema.json','profile':'schemas/profile.schema.json','report':'schemas/report.schema.json','envelope':'source-contracts/SemanticEventEnvelope.v0.1.json','request':'source-contracts/CommitIngressRequest.v0.1.json'}
QUALIFICATIONS=['Only conditional offline conformance is established. Trusted pins and immutable proof selection are independent caller configuration, not fields authenticated by this proof.','Profile cases classify exact described consequence/subtype combinations. No general natural-language classifier, event occurrence, acceptance or authorization is established.','Availability is checked against the independently selected owner context and closed input order. Actual producer execution, clock trust, owner identity and runtime admission are not established.','The proof never requires a dependent verdict, its trace, a final assertion effect or this attempt receipt. Exact reevaluation does not authorize commit/result replay.']

MAX_BYTES=2*1024*1024
MAX_DEPTH=64
JCS_FILES={'__init__.py':'fa44927afd547caf7547247078bcf28863d1e69caf116d258c532b3f20ffd154','_impl.py':'c25bc3a046528482d53bee3487b837f31dd9c05f33e8f13288c7aab320932cec'}
class InputFault(ValueError):pass
def sha(raw):return hashlib.sha256(raw).hexdigest()
def strict(raw):
    if not isinstance(raw,bytes) or not raw:raise InputFault('MISSING_OR_NONBYTE_INPUT')
    if len(raw)>MAX_BYTES:raise InputFault('INPUT_SIZE_LIMIT')
    depth=0;quoted=False;escaped=False
    for byte in raw:
        if quoted:
            if escaped:escaped=False
            elif byte==92:escaped=True
            elif byte==34:quoted=False
        elif byte==34:quoted=True
        elif byte in (91,123):
            depth+=1
            if depth>MAX_DEPTH:raise InputFault('INPUT_DEPTH_LIMIT')
        elif byte in (93,125):depth-=1
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise InputFault('DUPLICATE_JSON_NAME')
            result[key]=value
        return result
    def bad_constant(value):raise InputFault('NON_JSON_NUMBER')
    try:return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=bad_constant)
    except (UnicodeError,json.JSONDecodeError,RecursionError) as e:raise InputFault('INVALID_UTF8_JSON') from e
def pointer(path):return ''.join('/'+str(v).replace('~','~0').replace('/','~1') for v in path)
def refs_are_local(value):
    if isinstance(value,dict):return all((k not in ('$ref','$dynamicRef','$recursiveRef')) and refs_are_local(v) for k,v in value.items())
    if isinstance(value,list):return all(refs_are_local(v) for v in value)
    return True

def _verify(proof_bytes, envelope_bytes, request_bytes, context_bytes, profile_bytes, *, trusted_pins, expected_proof_binding, use_mode='INITIAL_EVALUATION', package_root=PACKAGE,source_root=None):
    """Verify exact source bytes and owner context; no resolver callback or network.

    trusted_pins is exactly {contractSha256, contextSha256, profileSha256}.
    expected_proof_binding is exactly {ref, digest}, from selected immutable input.
    Neither object may be populated by trusting corresponding proof claims.
    """
    raws=dict(proof=proof_bytes,envelope=envelope_bytes,request=request_bytes,context=context_bytes,profile=profile_bytes)
    report={'schemaVersion':'ofarm.eventClassificationVerificationReport.v0.1','status':'INPUT_ERROR','contractId':CID,'verificationMode':'OFFLINE_CANDIDATE_CONFORMANCE','runtimeAdmission':'NOT_ESTABLISHED','useMode':use_mode if isinstance(use_mode,str) else '<invalid>','proofBinding':None,'inputDigests':{k:None for k in raws},'rawInputSha256':{k:sha(v if isinstance(v,bytes) else b'') for k,v in raws.items()},'checkedRules':[],'errors':[],'classification':None,'qualifications':QUALIFICATIONS.copy()}
    def error(code,document,p='',detail=None):
        item={'code':code,'document':document,'pointer':p}
        if detail is not None:item['detail']=detail
        report['errors'].append(item)
    def check(ok,code,document,p='',detail=None):
        if not ok:error(code,document,p,detail)
        return ok
    def mark(rule):
        if rule not in report['checkedRules']:report['checkedRules'].append(rule)
    try:
        import rfc8785
        from jsonschema import Draft202012Validator,FormatChecker
        from jsonschema.exceptions import SchemaError
    except ImportError:
        report['status']='DEPENDENCY_UNAVAILABLE';error('MISSING_LOCAL_DEPENDENCY','package');return report
    try:
        if version('rfc8785')!='0.1.4' or any(sha((Path(rfc8785.__file__).parent/name).read_bytes())!=pin for name,pin in JCS_FILES.items()):
            raise InputFault('UNSUPPORTED_RFC8785_IMPLEMENTATION')
        if rfc8785.dumps({'z':-0.0,'a':1e-7,'\ue000':2,'\U00010000':3})!=b'{"a":1e-7,"z":0,"\xf0\x90\x80\x80":3,"\xee\x80\x80":2}':
            raise InputFault('RFC8785_BEHAVIOR_MISMATCH')
    except (PackageNotFoundError,OSError,InputFault,TypeError,ValueError) as exc:
        report['status']='DEPENDENCY_UNAVAILABLE';error('RFC8785_DEPENDENCY_MISMATCH','package',detail=type(exc).__name__);return report
    def digest(v):return 'sha256:'+sha(rfc8785.dumps(v))
    if not isinstance(trusted_pins,dict) or set(trusted_pins)!= {'contractSha256','contextSha256','profileSha256'} or any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in trusted_pins.values()):
        error('INVALID_INDEPENDENT_PINS','trustedPins');return report
    if not isinstance(expected_proof_binding,dict) or set(expected_proof_binding)!= {'ref','digest'} or not isinstance(expected_proof_binding.get('ref'),str) or not re.fullmatch('[A-Za-z0-9._:/-]+',expected_proof_binding['ref']) or not isinstance(expected_proof_binding.get('digest'),str) or not re.fullmatch('sha256:[0-9a-f]{64}',expected_proof_binding['digest']):
        error('INVALID_PROOF_SELECTOR','expectedProofBinding');return report
    if use_mode not in ['INITIAL_EVALUATION','EXACT_REEVALUATION']:
        error('UNKNOWN_USE_MODE','useMode');return report
    try:
        contract_raw=(Path(package_root)/'contract.json').read_bytes()
        if not check(sha(contract_raw)==trusted_pins['contractSha256'],'CONTRACT_PIN_MISMATCH','contract'):return report
        contract=strict(contract_raw)
        if not isinstance(contract,dict) or contract.get('contractId')!=CID or contract.get('version')!='0.1' or contract.get('requiredRules')!=RULES:
            error('UNSUPPORTED_CONTRACT','contract');return report
        if not check(contract.get('contractDigest')==digest({k:v for k,v in contract.items() if k!='contractDigest'}),'CONTRACT_SELF_DIGEST_MISMATCH','contract','/contractDigest'):return report
        if not isinstance(contract.get('schemas'),dict) or set(contract['schemas'])!=set(SCHEMA_PATHS):
            error('SCHEMA_CLOSURE_MISMATCH','contract','/schemas');return report
        code=contract.get('verificationCode')
        if not isinstance(code,dict) or set(code)!={'verify_event_proof.py','report_contract.py'}:
            error('VERIFIER_CLOSURE_MISMATCH','contract');return report
        if Path(report_contract.__file__).resolve()!=Path(__file__).resolve().parent/'report_contract.py':
            error('REPORT_MODULE_LOCATION_MISMATCH','package');return report
        for filename,pin in code.items():
            if not check(sha((Path(__file__).resolve().parent/filename).read_bytes())==pin,'VERIFIER_PIN_MISMATCH','package',filename):return report
        schemas={}
        for key,path in SCHEMA_PATHS.items():
            binding=contract['schemas'][key]
            if not isinstance(binding,dict) or binding.get('path')!=path:
                error('SCHEMA_PATH_MISMATCH','contract','/schemas/'+key);return report
            raw=(Path(package_root)/path).read_bytes()
            if not check(sha(raw)==binding.get('sha256'),'SCHEMA_PIN_MISMATCH',key):return report
            schema=strict(raw)
            if not isinstance(schema,dict) or schema.get('$id')!=binding.get('schemaId') or not refs_are_local(schema):
                error('SCHEMA_ID_OR_REFERENCE_MISMATCH',key);return report
            Draft202012Validator.check_schema(schema);schemas[key]=schema
        if schemas['report']!=REPORT_SCHEMA:
            report['status']='DEPENDENCY_UNAVAILABLE';error('REPORT_SCHEMA_MISMATCH','report');return report
        source_paths=['sources/event-grammar.md','sources/event-ingress-rfc.md','sources/platform.md','sources/constitution.md']
        sources=contract.get('semanticSources')
        if not isinstance(sources,list) or len(sources)!=len(source_paths) or any(not isinstance(v,dict) for v in sources) or sorted(v.get('path','') for v in sources)!=sorted(source_paths):
            error('SEMANTIC_SOURCE_CLOSURE_MISMATCH','contract');return report
        for source in sources:
            if not isinstance(source,dict) or source.get('path') not in ['sources/event-grammar.md','sources/event-ingress-rfc.md','sources/platform.md','sources/constitution.md']:
                error('SEMANTIC_SOURCE_PATH_MISMATCH','contract');return report
            if not check(sha((Path(package_root if source_root is None else source_root)/source['path']).read_bytes())==source.get('sha256'),'SEMANTIC_SOURCE_PIN_MISMATCH','contract'):return report
    except (OSError,InputFault,ValueError,TypeError,OverflowError,KeyError,SchemaError,RecursionError) as exc:
        error('PACKAGE_UNAVAILABLE_OR_INVALID','package',detail=type(exc).__name__);report['status']='DEPENDENCY_UNAVAILABLE';return report
    mark('PACKAGE_PINS')
    fmt=FormatChecker()
    @fmt.checks('date-time',raises=(ValueError,TypeError))
    def date_time(value):
        if not isinstance(value,str):return True
        if not re.fullmatch(r'[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])[Tt](?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\.[0-9]+)?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])',value):return False
        datetime.fromisoformat(value.upper().replace('Z','+00:00'));return True
    def shape(key,value):
        errors=sorted(Draft202012Validator(schemas[key],format_checker=fmt).iter_errors(value),key=lambda e:(pointer(e.absolute_path),e.message))
        for e in errors:error('SCHEMA_INVALID',key,pointer(e.absolute_path),e.message)
        return not errors
    if not shape('contract',contract):return report
    values={}
    for name,raw in raws.items():
        try:
            value=strict(raw);value_digest=digest(value)
            values[name]=value;report['inputDigests'][name]=value_digest
        except (InputFault,ValueError,TypeError,OverflowError,RecursionError) as exc:
            error(str(exc) if isinstance(exc,InputFault) else 'NON_CANONICAL_VALUE',name)
    mark('STRICT_JSON')
    if len(values)!=len(raws):return report
    check(report['rawInputSha256']['context']==trusted_pins['contextSha256'],'CONTEXT_PIN_MISMATCH','context');mark('INDEPENDENT_CONTEXT_PIN')
    check(report['rawInputSha256']['profile']==trusted_pins['profileSha256'],'PROFILE_PIN_MISMATCH','profile');mark('INDEPENDENT_PROFILE_PIN')
    valid=[shape(name,value) for name,value in values.items()];mark('EXACT_SCHEMA_CLOSURE')
    if not all(valid) or report['errors']:
        report['status']='FAIL';return report
    proof,envelope,request,context,profile=(values[x] for x in ['proof','envelope','request','context','profile'])
    actual_proof={'ref':proof['proofId'],'digest':digest(proof)};report['proofBinding']=actual_proof
    check(actual_proof==expected_proof_binding,'PROOF_SELECTOR_MISMATCH','proof');mark('EXACT_PROOF_SELECTOR')
    cb={'ref':CID,'digest':contract['contractDigest']}
    for name,value in [('proof',proof),('context',context),('profile',profile)]:check(value['contractBinding']==cb,'CONTRACT_BINDING_MISMATCH',name,'/contractBinding')
    mark('CONTRACT_BINDINGS')
    eb={'ref':envelope['semanticEventId'],'digest':digest(envelope)};rb={'ref':request['requestId'],'digest':digest(request)};pb={'ref':profile['profileId'],'digest':digest(profile)};ob={'ref':context['contextId'],'digest':digest(context)}
    for name,value in [('proof',proof),('context',context)]:
        for k,expected in [('envelopeBinding',eb),('ingressRequestBinding',rb),('classificationProfileBinding',pb)]:check(value[k]==expected,'INPUT_BINDING_MISMATCH',name,'/'+k)
        for k,rawname in [('envelopeBytesSha256','envelope'),('ingressRequestBytesSha256','request')]:check(value[k]==report['rawInputSha256'][rawname],'SOURCE_BYTES_MISMATCH',name,'/'+k)
    mark('WHOLE_INPUT_DIGESTS');mark('EXACT_SOURCE_BYTES')
    check(proof['ownerContextBinding']==ob,'OWNER_CONTEXT_BINDING_MISMATCH','proof','/ownerContextBinding')
    check(proof['proofId']==context['expectedProofId'],'OWNER_PROOF_ID_MISMATCH','proof','/proofId');mark('OWNER_CONTEXT')
    check(request['semanticEventRef']==envelope['semanticEventId'],'REQUEST_EVENT_MISMATCH','request','/semanticEventRef')
    check(request['targetScopes']==context['expectedTargetScopes'],'REQUEST_SCOPE_MISMATCH','request','/targetScopes')
    mark('REQUEST_CONTEXT')
    caseids=[c['caseId'] for c in profile['cases']]
    signatures=[(c['dominantSemanticConsequence'],json.dumps(c['subtype'],sort_keys=True)) for c in profile['cases']]
    check(len(caseids)==len(set(caseids)) and len(signatures)==len(set(signatures)),'AMBIGUOUS_CLASSIFICATION_PROFILE','profile','/cases')
    source_bindings={('ofarm:event-grammar:v0.1','sha256:'+s['sha256']) for s in contract['semanticSources'] if s['path']=='sources/event-grammar.md'}
    for i,c in enumerate(profile['cases']):check((c['semanticSourceBinding']['ref'],c['semanticSourceBinding']['digest']) in source_bindings,'CLASSIFICATION_SOURCE_MISMATCH','profile','/cases/'+str(i)+'/semanticSourceBinding')
    subtype={'presence':'PRESENT','value':envelope['eventSubtypeId']} if 'eventSubtypeId' in envelope else {'presence':'ABSENT'}
    matches=[c for c in profile['cases'] if c['dominantSemanticConsequence']==envelope['dominantSemanticConsequence'] and c['subtype']==subtype]
    check(len(matches)==1,'CLASSIFICATION_CASE_NOT_EXACT','envelope');mark('UNIQUE_CASE_SELECTION')
    if len(matches)==1:
        selected=matches[0];expected={'caseId':selected['caseId'],'authoritativePrimaryFamily':selected['authoritativePrimaryFamily'],'commitClass':context['expectedCommitClass'],'dominantSemanticConsequence':selected['dominantSemanticConsequence'],'subtype':selected['subtype']}
        check(selected['caseId']==context['selectedCaseId'],'OWNER_CASE_SELECTION_MISMATCH','context','/selectedCaseId')
        check(proof['classification']==expected,'CLASSIFICATION_MISMATCH','proof','/classification')
        check(envelope['primaryEventFamily']==selected['authoritativePrimaryFamily'],'FAMILY_MISMATCH','envelope','/primaryEventFamily')
        report['classification']=expected
    mark('INDEPENDENT_CLASSIFICATION');mark('COMPLETE_DOMINANT_CONTEXT');mark('FAMILY_EQUALITY')
    check(proof['classification']['commitClass']==request['commitClass']==context['expectedCommitClass'],'COMMIT_CLASS_MISMATCH','proof','/classification/commitClass');mark('COMMIT_CLASS_EQUALITY')
    check(proof['productionMode']==context['productionMode'],'PRODUCTION_MODE_MISMATCH','proof','/productionMode')
    check(proof['completionMilestone']==context['requiredMilestone']==MILESTONE and context['inputRoles']==INPUT_ROLES,'PRE_VERDICT_ORDER_MISMATCH','context');mark('PRE_VERDICT_INPUT_CLOSURE')
    check(proof['reuseRule']==context['reuseRule']==REUSE and use_mode in context['permittedUseModes'],'REUSE_NOT_ALLOWED','context','/permittedUseModes');mark('EXACT_REUSE')
    report['status']='FAIL' if report['errors'] else 'CONDITIONAL_CONFORMANCE_PASS'
    return report

def _report_matches(schema,value):
    """Evaluate only the finite keywords in the frozen owned report schema.

    Kept independent of optional dependencies so dependency-failure reports are
    checked too. This is not a JSON Schema engine exposed for other documents.
    The suite cross-checks every report with Draft202012Validator.
    """
    allowed={'$schema','$id','title','oneOf','type','const','enum','pattern','minLength','additionalProperties','properties','required','minItems','uniqueItems','items'}
    if set(schema)-allowed:raise RuntimeError('Unsupported owned report schema keyword')
    if 'oneOf' in schema:return sum(_report_matches(s,value) for s in schema['oneOf'])==1
    if 'const' in schema and value!=schema['const']:return False
    if 'enum' in schema and value not in schema['enum']:return False
    typ=schema.get('type')
    if typ=='null':return value is None
    if typ=='string':
        return isinstance(value,str) and len(value)>=schema.get('minLength',0) and ('pattern' not in schema or re.search(schema['pattern'],value) is not None)
    if typ=='object':
        return isinstance(value,dict) and set(schema.get('required',[]))<=set(value) and (schema.get('additionalProperties') is not False or set(value)<=set(schema['properties'])) and all(_report_matches(schema['properties'][k],v) for k,v in value.items())
    if typ=='array':
        return isinstance(value,list) and len(value)>=schema.get('minItems',0) and (not schema.get('uniqueItems') or all(value[i] not in value[:i] for i in range(len(value)))) and all(_report_matches(schema['items'],v) for v in value)
    return typ is None

def verify(proof_bytes,envelope_bytes,request_bytes,context_bytes,profile_bytes,*,trusted_pins,expected_proof_binding,use_mode='INITIAL_EVALUATION',package_root=PACKAGE,source_root=None):
    """Public API. Every result, including early failures, matches REPORT_SCHEMA."""
    report=_verify(proof_bytes,envelope_bytes,request_bytes,context_bytes,profile_bytes,trusted_pins=trusted_pins,expected_proof_binding=expected_proof_binding,use_mode=use_mode,package_root=package_root,source_root=source_root)
    if not _report_matches(REPORT_SCHEMA,report):raise RuntimeError('Internal owned report schema violation')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['proof','envelope','request','context','profile']:p.add_argument('--'+name,type=Path,required=True)
    for name in ['contract','context','profile']:p.add_argument('--trusted-'+name+'-sha256',required=True)
    p.add_argument('--expected-proof-ref',required=True);p.add_argument('--expected-proof-digest',required=True);p.add_argument('--use-mode',default='INITIAL_EVALUATION');p.add_argument('--dependency-dir',type=Path);p.add_argument('--output',type=Path);p.add_argument('--package-root',type=Path,default=PACKAGE)
    p.add_argument('--source-root',type=Path)
    a=p.parse_args()
    if a.dependency_dir:sys.path.insert(0,str(a.dependency_dir.resolve()))
    def raw(path):
        try:return path.read_bytes()
        except OSError:return None
    r=verify(*(raw(getattr(a,k)) for k in ['proof','envelope','request','context','profile']),trusted_pins={'contractSha256':a.trusted_contract_sha256,'contextSha256':a.trusted_context_sha256,'profileSha256':a.trusted_profile_sha256},expected_proof_binding={'ref':a.expected_proof_ref,'digest':a.expected_proof_digest},use_mode=a.use_mode,package_root=a.package_root,source_root=a.source_root)
    rendered=json.dumps(r,indent=2,ensure_ascii=False)+'\n'
    if a.output:a.output.write_text(rendered)
    else:print(rendered,end='')
    return {'CONDITIONAL_CONFORMANCE_PASS':0,'FAIL':1,'INPUT_ERROR':2,'DEPENDENCY_UNAVAILABLE':3}[r['status']]
if __name__=='__main__':raise SystemExit(main())
