# OFARM Security Audit Credential Diagnostic Representation RFC v0.1

**Status:** decision versions 2 and 3 were implemented and merged through pull
requests #349 and #354. Post-merge review #5058662084 demonstrates one narrower
parenthesized-annotation conformance defect. Decision version 4 is proposed in
Delivery issue #357 and amended after Phase A reviews #5059132827 and
#5059215166 identified in-boundary declaration-shape and declaration-completeness
blockers. Phase B is unauthorized pending amended exact-head Phase A re-review
and later task-user approval.

**Decision:**
`ISSUE192-SECURITY-AUDIT-CREDENTIAL-DIAGNOSTIC-REPRESENTATION-001`

**Decision version:** 4 proposed; versions 2 and 3 remain historical approved
and merged decisions

**Version history:** version 1 was an unapproved, pre-pull-request task draft.
Version 2 superseded it because the bounded Phase A review required two
additional derived carriers and a narrower captured-locals invariant. The task
user approved version 2, and pull request #349 merged its implementation.
Version 3 is a new decision because post-merge review demonstrated that the
`CDR-006` checker implementation did not recognize every class-namespace
binding form, and the correction required a new named pull request. The task
user approved version 3 after its bounded scope-transition review. Version 3
preserved the accepted five-carrier runtime posture and changed only structural
conformance enforcement. Version 4 is a new decision because post-merge review
of merged version 3 demonstrated that the checker conflates a parenthesized
annotated name with a real dataclass field declaration and must bind a new
Delivery issue and pull request. Its initial Phase A contract was amended before
approval because review #5059132827 demonstrated that `simple == 1` proves an
annotation key but does not alone prove the approved dataclass declaration
shape. A second amendment follows review #5059215166 because approved direct
declarations alone do not exclude an additional simple annotated field inside
target-class control flow.

**Issue context:** Tracking Epic
[#192](https://github.com/samovers/OFARM2/issues/192), original Delivery outcome
[#350](https://github.com/samovers/OFARM2/issues/350), completed correction
Delivery issue [#352](https://github.com/samovers/OFARM2/issues/352), and current
correction Delivery issue [#357](https://github.com/samovers/OFARM2/issues/357)

**Version-3 base:** `a1e2d343b59a5715e07fcb550a459b61dc6541da`

**Version-4 base:** `774823336f25e4f9cef79fd7b6f51d1dda3d6745`

**Merged version-2 pull request:**
[#349](https://github.com/samovers/OFARM2/pull/349)

**Merged version-3 pull request:**
[#354](https://github.com/samovers/OFARM2/pull/354)

**Draft version-4 pull request:**
[#358](https://github.com/samovers/OFARM2/pull/358)

**Version-2 approval evidence:** the task user approved the exact sentence `I approve
OFARM2 decision ISSUE192-SECURITY-AUDIT-CREDENTIAL-DIAGNOSTIC-REPRESENTATION-001
version 2.` on 2026-08-29. The
[pull-request navigation copy](https://github.com/samovers/OFARM2/pull/349#issuecomment-5461601281)
is non-authoritative; the task record remains the approval authority.

**Version-3 approval evidence:** after the zero-Blocker bounded reviews of the
RFC-only head, the task user approved the exact sentence `I approve OFARM2
decision ISSUE192-SECURITY-AUDIT-CREDENTIAL-DIAGNOSTIC-REPRESENTATION-001
version 3.` on 2026-08-29. The task record remains the approval authority.
Version-2 approval did not transfer to the post-merge correction.

**Primary trust boundary:** credential-bearing diagnostic-representation
structural conformance for the five exact dataclass carriers already reached by
the production runtime, process-crash reconciliation, and store-loss recovery
compositions

**Historical version-2 maximum implementation path envelope:**

1. `docs/rfcs/OFARM_Security_Audit_Credential_Diagnostic_Representation_RFC_v0_1.md`
2. `kernel/runtime_config.py`
3. `deployment/postgresql/security_audit_process_crash.py`
4. `deployment/postgresql/security_audit_store_loss.py`
5. `kernel/tests/test_security_audit_credential_diagnostics.py`
6. `conformance/rewrite_architecture_check.py`
7. `kernel/tests/test_rewrite_architecture_check.py`
8. `conformance/review_baseline_test_inventory.json`

**Version-3 expected repository areas, as scope prediction rather than approval
authority:**

1. `docs/rfcs/OFARM_Security_Audit_Credential_Diagnostic_Representation_RFC_v0_1.md`
2. `conformance/rewrite_architecture_check.py`
3. `kernel/tests/test_rewrite_architecture_check.py`
4. `conformance/review_baseline_test_inventory.json`, only when mechanically
   required by changed canonical test node IDs

This contract creates no OFARM authority. It does not authorize deployment,
production access, production composition, release, certification, current
compliance, issue closure, or a change to credential custody. The production
composition remains unauthorized and non-deployable.

## 1. Problem and goal

Five immutable dataclasses on supported security-audit paths currently receive
field-bearing representations generated by `dataclasses`:

1. `kernel.runtime_config.RuntimeConfig`;
2. `ProcessCrashReconciliationSecrets`;
3. `StoreLossRecoverySecrets`;
4. the store-loss derived `_Routes`; and
5. the store-loss derived `_ValidatedInvocation`.

The first three directly hold password-bearing PostgreSQL routes or login
passwords. `_bounded_dsn()` preserves password-bearing connection parameters
when it creates every `_Routes` value. `_ValidatedInvocation` then retains
those routes and the login-password tuple. Ordinary representation of any of
these objects can therefore disclose complete credential values. The same-type
assertion explanation produced by the repository-pinned pytest can also inspect
generated-dataclass equality field by field and print a differing secret.

No current production log statement has been found to demonstrate that a leak
already occurred. The defect is the mechanically reachable, field-bearing
diagnostic surface itself.

The goal is to make all five exact carriers opaque on a closed set of ordinary
diagnostic representation surfaces while preserving their complete value
equality, generated frozen hash, construction, validation, runner inputs,
governed outputs, database effects, and state-machine behavior.

The result establishes only direct representation hardening for the five named
objects. It does not establish universal secret redaction for arbitrary Python
locals, raw strings, mappings, serialization, debuggers, or crash reporters.

## 2. Learning value

This slice reduces a demonstrated accidental-disclosure risk without adding a
redaction framework or changing credential flow. It validates a narrow Python
boundary rule: a credential-bearing immutable carrier can inherit opaque
`object` display while retaining exact value semantics through one explicit,
all-field equality operation.

The focused evidence also distinguishes two surfaces that are otherwise easy
to conflate:

- object representation, which this decision can close; and
- independently retained raw credential locals, which require a different and
  broader runtime-frame sanitation design.

## 3. Non-goals

This decision does not:

- change how any password, DSN, KMS resource name, signing-evidence path, or
  other configuration value is created, validated, stored, passed, used, or
  destroyed;
- change credential ownership, secret distribution, provider authority,
  PostgreSQL role authority, route authority, or deployment authority;
- sanitize a traceback frame that separately retains an environment mapping,
  raw DSN or password local, parsed conninfo mapping, password tuple, or other
  derived credential value;
- change `RuntimeConfig.from_env()`, which currently retains an environment
  dictionary while constructing configuration;
- change process-crash validation or execution locals such as the parsed
  `observed` mapping or raw `conninfo` string;
- change store-loss validation or execution locals such as `dsn_values`,
  `pairs`, raw route strings, or other ordinary containers;
- protect explicit field access, deliberate field printing, `asdict`,
  `astuple`, JSON conversion, pickling, debugger expansion, private-state
  inspection, or a caller-created serialization;
- claim that an arbitrary logging or crash-reporting system is safe merely
  because these five object representations are opaque;
- add a safe-summary or redacted-summary API;
- change runtime startup, readiness, health, gap, process-crash, store-loss,
  migration, provisioning, transaction, report, or command behavior;
- change SQL, migrations, database roles, grants, schemas, credentials, or
  state-machine authority;
- change the bounded export operation or add protected export-output custody
  and delivery;
- compose or evidence production clocks, timers, routes, providers, IAM, or
  secret custody;
- change the completed issue #334 package-initializer reachability correction;
- define complete execution-root or source-capability governance; or
- close, reopen, or otherwise change issue #192 automatically.

A broader guarantee for real runner frames is a different trust boundary. It
would require redesigning or sanitizing every raw local-value path and is not a
review requirement for this pull request.

## 4. Trust model

### 4.1 Protected assets

The protected assets are the exact password-bearing values stored in or
reachable through the five target carriers:

- the six current password-capable `RuntimeConfig` PostgreSQL fields;
- the process-crash control conninfo;
- the three store-loss input DSNs and complete login-password tuple;
- the five password-preserving store-loss derived routes; and
- the `_ValidatedInvocation` routes and login-password tuple.

The absence of those exact values from the closed accepted diagnostic surface
is the security property. Class names, module names, ordinary object identity
addresses, non-secret fixed exception text, and test-owned fictional canary
labels are not protected by this decision unless they equal a protected exact
value.

### 4.2 Trusted components and inputs

This decision trusts only:

- CPython 3.12.13 object, exception, traceback, dataclass, equality, and hash
  semantics used by the repository baseline;
- pytest 9.1.1 from `requirements-review-baseline.lock` for the assertion
  rendering evidence;
- the exact five class declarations and field inventories authenticated by the
  existing `PythonSourceSnapshotV1` architecture-check input;
- the existing production construction and validation paths for those values;
- the exact test-owned fictional credential canaries; and
- the architecture checker running over detached ASTs from the authenticated
  source snapshot rather than rereading repository paths.

The tests do not trust a heuristic based on field names such as `password`,
`secret`, or `dsn`. The exact path, class, protected-field, and complete-field
maps are the authorities.

### 4.3 Untrusted actors and inputs

The following are untrusted within the stated surface:

- a caller that passes a target carrier to ordinary Python representation,
  formatting, a nested built-in container, or an exception;
- a synthetic failing frame whose only secret-bearing local is one target
  carrier instance;
- a same-type pytest equality assertion involving unequal target instances;
- future edits that restore a generated repr, add a custom display method,
  weaken exact-type equality, omit a field, or replace the exact architecture
  inventory with a heuristic; and
- all fictional DSN and password values used as canaries.

### 4.4 Explicitly excluded attacker capabilities

The following are outside this decision:

- arbitrary in-process mutation or replacement of classes or instances;
- local source substitution after the reviewed commit is selected;
- compromised CPython, pytest, dataclasses, Psycopg, or other dependencies;
- arbitrary filesystem mutation during verification;
- repository-owner, host, kernel, debugger, profiler, crash-reporter, database
  administrator, provider administrator, or operator compromise;
- explicit credential attribute access or deliberate serialization; and
- traceback frames that hold raw credential values independently of a target
  carrier.

Opaque representation is defense against routine diagnostic expansion, not a
security boundary against an operator or arbitrary code executing in process.

## 5. Authority map

| Decision | Sole authority | Rejected alternate or duplicate authority |
| --- | --- | --- |
| Target class inventory | Exact path/class map in the architecture checker, matched against the five declarations in the authenticated snapshot | Credential-name heuristic, import graph guess, test list alone |
| Protected value inventory | Exact protected-field tuple for each class in this RFC and checker | Substring matching for `password`, `secret`, `dsn`, or `conninfo` |
| Complete equality inventory | Every declared dataclass field in source declaration order, authenticated independently of the protected-field tuple | Protected fields alone, helper-selected subset, shadow tuple, `__dict__`, `asdict` |
| Ordinary object display | Inherited `object` representation caused by `repr=False` and absence of class display methods | Custom redactor, partial field repr, safe-summary fallback |
| Same-type value equality | One explicit exact-type, all-declared-field `__eq__` on each target class | Generated dataclass equality, identity equality, subclass equality, selected-field equality |
| Hash behavior | Frozen-dataclass generated hash over the unchanged comparable fields | `unsafe_hash=True`, class-defined `__hash__`, identity hash |
| Accepted diagnostic surface | Closed projection in section 6.3 and focused canary test | Unbounded log, debugger, serialization, or crash-reporting claim |
| Architecture verdict | Existing rewrite architecture checker over one authenticated `PythonSourceSnapshotV1` and its detached ASTs | Direct filesystem reread, regex-only scan, test result alone |
| Runner and database behavior | Existing runtime, process-crash, and store-loss code and tests | Diagnostic output treated as runtime authority |
| Test pass or failure | Repository-pinned pytest execution at the exact reviewed head | Design prose, skipped test, different pytest version |

No legacy representation API, redaction helper, safe-summary alias, alternate
write path, or compatibility shim is introduced.

## 6. State machine and ordering

### 6.1 Carrier lifecycle

Each target carrier remains in the existing operational lifecycle:

```text
INPUTS_RECEIVED
  -> existing validation and normalization
VALIDATED
  -> immutable target carrier constructed
CARRIER_AVAILABLE
  -> existing runtime or runner consumption
CONSUMED
```

This decision adds no operational transition and no side effect. Construction
signatures and validation run before any existing runtime or database side
effect exactly as they do at the reviewed base.

### 6.2 Diagnostic branches

When Python asks a constructed target carrier for ordinary display:

```text
CARRIER_AVAILABLE
  -> DISPLAY_REQUESTED
  -> inherited object representation
OPAQUE_DISPLAY_COMPLETE
```

When Python asks for equality:

```text
CARRIER_AVAILABLE
  -> EQUALITY_REQUESTED
      -> different exact class -> NotImplemented
      -> same exact class -> compare every declared field once in order
  -> EQUALITY_COMPLETE
```

No representation request may read a declared field through a generated or
custom class display method. No equality request may omit a declared field,
accept a subclass as the same exact carrier, or use a second field inventory.

The dataclass decorator observes `frozen=True`, `eq=True` by default or
explicitly, no `unsafe_hash=True`, and one explicit `__eq__`; it therefore
continues to generate the frozen value hash. There is no class-defined
`__hash__`.

### 6.3 Closed accepted diagnostic projection

For each target carrier, the complete accepted projection is exactly:

```text
repr(carrier)
str(carrier)
format(carrier)
f"{carrier!r}"
"%s" % carrier
"%r" % carrier
repr((carrier,))
repr([carrier])
repr({"carrier": carrier})
str(Exception(carrier))
repr(Exception(carrier))
normal traceback rendering for Exception(carrier)
TracebackException(..., capture_locals=True) for the bounded frame below
pinned-pytest same-type equality assertion output
```

The accepted captured-locals evidence uses a synthetic failing frame whose
only secret-bearing local is one target carrier instance. No raw credential
attribute, environment mapping, parsed conninfo mapping, DSN/password local,
serialized copy, derived route outside the target inventory, or password tuple
is separately present in that frame.

The test closes this projection by formatting every item into bytes or text and
requiring every exact canary value to be absent. It does not broaden the
accepted surface through arbitrary recursive inspection.

### 6.4 Forbidden transitions

The following are forbidden:

- restoring generated field-bearing repr on any target class;
- adding `__repr__`, `__str__`, or `__format__` to a target class;
- using partial field-level `repr=False` while another field can reach a
  credential-bearing object;
- relying on generated dataclass equality for a target class;
- changing equality to identity, protected-field-only comparison, or subclass
  acceptance;
- defining `unsafe_hash=True` or a class `__hash__`;
- treating explicit serialization or separately retained raw locals as passed
  acceptance evidence; and
- changing runtime or database behavior to make a representation test pass.

## 7. Invariants and acceptance criteria

### `CDR-001` — complete five-carrier opaque posture

Each exact target class remains `frozen=True` and `slots=True`, sets
`repr=False`, uses `eq=True` or its default equivalent, does not set
`unsafe_hash=True`, defines no `__hash__`, `__repr__`, `__str__`, or
`__format__`, and defines exactly one explicit `__eq__`.

### `CDR-002` — exact protected values absent from the closed surface

For every target class, every exact fictional value placed in every protected
field is absent from every item in the section 6.3 accepted projection.
Class-wide opacity is required even when a non-protected field differs.

### `CDR-003` — bounded traceback evidence is honest

Normal exception traceback rendering and captured-locals rendering omit every
protected canary only for the synthetic frame whose sole secret-bearing local
is the target carrier. The evidence and report explicitly exclude frames that
separately retain raw or serialized credentials.

### `CDR-004` — same-type pytest assertion output is opaque

Under repository-pinned CPython 3.12.13 and pytest 9.1.1, an assertion between
unequal instances of each exact target class does not display a protected
canary. The evidence must exercise pytest assertion rendering, not merely
`AssertionError` construction.

### `CDR-005` — equality and generated-hash semantics are preserved

For every target class, `__eq__` rejects a different exact class through
`NotImplemented` and compares two tuples that enumerate every declared field
exactly once, in declaration order, with identical left and right inventories.
Equal clones compare equal and have equal generated hashes. Changing any one
declared field makes instances unequal. No hash-collision absence is claimed.

### `CDR-006` — exact architecture guard fails closed

The rewrite architecture checker authenticates the five exact paths and
classes, their exact protected fields, their complete declared fields, their
decorator and method posture, and the exact equality structure from the
existing source snapshot. A missing path or class, extra or omitted declared
field, changed order, missing protected field, generated repr/equality, custom
display, custom hash, unsafe hash, subset equality, helper-selected equality,
or direct-filesystem fallback fails the checker.

### `CDR-007` — governed behavior and effects do not change

Constructor signatures, fields, immutability, validation, governed runner
inputs, governed command/report outputs, database effects, and state-machine
side effects remain unchanged. Only the explicitly enumerated diagnostic
representation surfaces change.

### `CDR-008` — supported derived credential carriers cannot bypass opacity

The store-loss path protects both input secrets and the two derived carriers.
Password-preserving `_Routes` and the `_ValidatedInvocation` that contains
routes and login passwords cannot retain generated field-bearing
representations. Adding a new credential-bearing dataclass to any of the three
governed modules requires an explicit contract amendment rather than silent
heuristic admission.

All invariants fail closed. A representation or checker ambiguity is a failed
test or architecture verdict, not permission to publish a partial diagnostic.

## 8. Negative cases

| Invariant | Supported entry and counterexample | Required result |
| --- | --- | --- |
| `CDR-001` | `kernel.api.create_app()` reaches `RuntimeConfig.from_env()`; a future edit removes `repr=False` from `RuntimeConfig` | Architecture and focused tests fail before the change can be accepted |
| `CDR-002` | A password-bearing configuration accepted by `RuntimeConfig.from_env()` is placed inside a list and represented; generated repr would expose one of the six DSNs | Exact DSN canary is absent; generated repr mutation fails |
| `CDR-003` | A supported carrier produced for `SecurityAuditProcessCrashReconciliationRunner.run()` is the sole secret-bearing local in a synthetic failing frame; generated repr would expose its conninfo in captured locals | Both bounded traceback projections omit the conninfo; the result makes no claim about `_execute(..., conninfo)` locals |
| `CDR-004` | Two unequal `StoreLossRecoverySecrets` values suitable for `SecurityAuditStoreLossRecoveryRunner.run()` differ only by one password and are compared by an asserted equality under pinned pytest | Assertion fails as expected, but its rendered output omits both password canaries |
| `CDR-005` | Two production-valid `RuntimeConfig` instances differ only in `signing_evidence_observer_public_key`; an equality implementation comparing only protected DSNs would call them equal | They compare unequal; equal clones compare equal and have equal generated hashes |
| `CDR-006` | The governed `rewrite_architecture_check.py` entry sees `_Routes` restored to generated equality or sees one route omitted from either equality tuple | Checker returns failure with a bounded target-class diagnostic |
| `CDR-007` | `SecurityAuditProcessCrashReconciliationRunner.run()` receives the same request and secret carrier before and after the correction, but a proposed fix changes validation or report bytes | Existing focused behavior tests fail; such a change is outside the allowed design |
| `CDR-008` | `SecurityAuditStoreLossRecoveryRunner.run()` validates input secrets, derives password-bearing `_Routes`, and wraps them in `_ValidatedInvocation`; only the public input carrier is made opaque | Architecture and representation tests fail because both derived target classes are mandatory |

The production reachability named above establishes why each carrier is in the
boundary. The focused diagnostic tests may construct valid fictional instances
or invoke the existing pure validation/derivation path without opening a
database connection. They may not mutate private fields or manufacture a claim
about a production state transition.

## 9. Proposed architecture and smallest change

### 9.1 Exact target and field inventories

Protected fields and equality fields are separate closed inventories:

| Source path and class | Protected fields | Complete equality fields in declaration order |
| --- | --- | --- |
| `kernel/runtime_config.py` — `RuntimeConfig` | `pg_dsn`, `tenant_readiness_pg_dsn`, `security_audit_readiness_pg_dsn`, `security_audit_authentication_pg_dsn`, `security_audit_request_router_pg_dsn`, `security_audit_control_pg_dsn` | `mode`, `deployment_image_digest`, `oidc_issuer`, `oidc_audience`, `oidc_jwks_url`, `pg_dsn`, `tenant_readiness_pg_dsn`, `security_audit_readiness_pg_dsn`, `security_audit_authentication_pg_dsn`, `security_audit_request_router_pg_dsn`, `security_audit_control_pg_dsn`, `correlation_hmac_kms_key_resource`, `tenant_capability_kid`, `signing_evidence_receipt_path`, `signing_evidence_observer_public_key` |
| `deployment/postgresql/security_audit_process_crash.py` — `ProcessCrashReconciliationSecrets` | `control_conninfo` | `control_conninfo` |
| `deployment/postgresql/security_audit_store_loss.py` — `StoreLossRecoverySecrets` | `admin_dsn`, `migrator_dsn`, `control_dsn`, `login_passwords` | `admin_dsn`, `migrator_dsn`, `control_dsn`, `login_passwords` |
| `deployment/postgresql/security_audit_store_loss.py` — `_Routes` | `admin_long`, `admin_short`, `admin_target_short`, `migrator_long`, `control_short` | `admin_long`, `admin_short`, `admin_target_short`, `migrator_long`, `control_short` |
| `deployment/postgresql/security_audit_store_loss.py` — `_ValidatedInvocation` | `routes`, `login_passwords` | `request`, `routes`, `login_passwords` |

The protected inventory determines which exact canaries must be absent. The
complete inventory independently owns equality preservation. A non-secret
field may never be omitted from equality merely because it is absent from the
protected tuple.

### 9.2 Class posture and equality shape

Each target decorator becomes equivalent to:

```python
@dataclass(frozen=True, slots=True, repr=False)
```

Each class owns one explicit equality operation with this closed structure:

```python
def __eq__(self, other: object) -> bool:
    if other.__class__ is not self.__class__:
        return NotImplemented
    other_carrier = cast(Self, other)
    return (
        self.field_1,
        self.field_2,
        # every declared field exactly once, declaration order
    ) == (
        other_carrier.field_1,
        other_carrier.field_2,
        # the identical field inventory and order
    )
```

The cast is static typing evidence only. It selects no fields and has no
authority. The checker accepts only exact-class rejection through
`NotImplemented` followed by direct tuple equality over the authenticated
declared fields. It rejects identity comparison, a helper-generated or
helper-selected tuple, `asdict`, `__dict__`, a shadow field constant, a
protected-field subset, duplicates, changed ordering, and extra expressions.

The classes define no custom display or hash operation. Because all existing
fields remain comparable and hashable, the frozen dataclass continues to
generate its value hash. `unsafe_hash=True` is forbidden.

### 9.3 Focused representation evidence

One new test module creates exact fictional canaries and exercises the complete
section 6.3 projection for all five carriers. Store-loss derived values are
obtained through the unchanged password-preserving derivation path or an
equivalent valid construction, so the evidence covers `_Routes` and
`_ValidatedInvocation` rather than merely their public input.

The test records every exact protected value before rendering. It checks the
closed projection as text and bytes without printing the canaries in a success
artifact. Failure diagnostics identify the target class and projection label,
not the forbidden value.

The pinned-pytest lane exercises real same-type assertion explanation. It
proves that the explicit equality method prevents pytest 9.1.1 from treating
the operation as generated dataclass equality and drilling into the differing
field. It does not claim behavior for another pytest version.

Equality tests create an equal clone and one-field-different instance for every
declared field of every target. They require equal clones to have equal hashes,
but do not require unequal instances to have distinct hashes.

### 9.4 Exact architecture conformance

The existing checker gains one private exact mapping from each of the three
source paths to target class, protected fields, and complete declared fields.
It consumes only the already authenticated `PythonSourceSnapshotV1` and the
detached AST map already owned by the checker.

For every target, the rule requires:

- one exact top-level class;
- the exact declared-field tuple;
- `frozen=True`, `slots=True`, and `repr=False`;
- `eq=True` or the default equivalent;
- no `unsafe_hash=True`;
- no class-defined `__hash__`, `__repr__`, `__str__`, or `__format__`;
- exactly one explicit `__eq__`;
- exact-type rejection returning `NotImplemented`;
- one direct tuple equality expression;
- each declared field exactly once on both sides; and
- identical declaration order on both sides.

The checker emits bounded path/class/rule diagnostics without source values.
It does not import or execute target modules, inspect runtime objects, or read
files outside the authenticated snapshot. Hostile checker tests cover every
accepted clause and representative attempts to bypass it.

### 9.5 Smallest coherent change

Class-wide `repr=False` is smaller and safer than annotating only current
credential fields because nested and future non-secret-looking carriers can
still reach credentials. Explicit all-field equality is the minimum addition
needed to preserve value semantics while preventing pinned pytest from
recognizing a generated dataclass equality function and expanding fields.

One focused test module and one exact architecture rule provide behavioral and
structural evidence. A redaction framework, safe-summary object, logging hook,
crash-reporter integration, wrapper type, secret string subclass, or runtime
local sanitation layer would broaden the boundary without improving the closed
claim.

## 10. Elegance audit

- **Sources of truth:** one source declaration per class, one exact checker map
  authenticated against those declarations, and one focused behavioral test
  projection. Protected and equality inventories are deliberately separate
  because they answer different questions.
- **Authoritative transitions:** existing construction and consumption paths
  remain the only operational transitions; the correction changes only Python
  representation and equality dispatch.
- **Duplicated fields:** no runtime field is added or copied. The checker and
  tests repeat exact inventories as independent conformance evidence, not
  runtime authority.
- **Compatibility surfaces:** none. There is no legacy repr, alias, opt-in
  redactor, feature flag, environment switch, or alternate equality path.
- **New abstractions:** no runtime abstraction. The checker may use one private
  descriptor value or tuple to keep the exact map bounded.
- **Deletion:** no accepted runtime behavior can be deleted. Generated repr and
  generated equality are replaced by the narrower posture; no obsolete custom
  code exists to remove.
- **Rewrite judgment:** a clean rewrite of the runners or runtime configuration
  would be disproportionate. Direct modification of the five declarations is
  clearer and smaller.

## 11. Pull request boundary

### 11.1 Primary boundary and intended pull request

Draft pull request #349 owns only credential-bearing diagnostic representation
non-disclosure. Phase A completed at
`07b51d4516e3ef201212dce9b45f8a590aad983c`, and the task user subsequently
approved this exact decision version for Phase B. Implementation remains
limited to the same capability, effects, authority, invariants, and pull
request.

### 11.2 Exact technical allowlist

The exact maximum implementation allowlist is the eight-path envelope in the
header. Every changed path must be in that set. The implemented change may use
fewer paths but may not add a ninth path without a new decision version.

The first Phase A commit changes only:

```text
docs/rfcs/OFARM_Security_Audit_Credential_Diagnostic_Representation_RFC_v0_1.md
```

The second RFC-only Phase A commit may change only that same path to bind the
created draft pull request and resolve Phase A review findings. No production,
test, checker, or inventory path may change before approval.

That pre-approval restriction is now satisfied. Phase B may change only the
remaining paths needed to implement and verify the approved boundary. The
eight-path envelope remains the maximum scope prediction; the approved
capability and trust boundary remain the semantic authority.

### 11.3 Dependencies and reviewer limits

The base already contains the unavailable-HMAC correction and completed issue
#334 initializer-reachability correction. There is no stacked pull-request
dependency.

Reviewers must not require this pull request to:

- sanitize actual runtime or runner frames that separately hold raw values;
- change credentials, custody, providers, databases, roles, SQL, migrations,
  deployment, or production composition;
- add output custody or delivery;
- add a general redaction API, logging framework, or crash reporter;
- expand the closed diagnostic projection; or
- close issue #192.

A demonstrated need for any such change stops this pull request for a separate
boundary or a new decision version.

### 11.4 Separate follow-ups

The following remain separate and do not block this decision:

1. a read-only issue #192 closure audit after all bounded corrections are
   merged;
2. protected export-output custody and delivery;
3. production clock, timer, route, provider, and secret-custody evidence,
   including parked draft PRs #322 and #323; and
4. complete execution-root and source-capability governance.

Issue #334 is completed at the reviewed base and is not reopened here. No new
issue is created by this contract.

## 12. Provisional design record

**Technical design:** Not provisional.

The exact opaque-representation and value-equality posture is the intended
pre-deployment design for these five carriers. Evidence requiring redesign
would be a supported diagnostic surface that bypasses inherited object
representation, a required equality consumer whose semantics differ from
all-field exact-type value equality, or a newly supported credential-bearing
carrier outside the exact inventory. Any of those requires a new decision
version before implementation expands.

The repository's AI-assisted approval mechanism remains provisional governance
under its existing accepted workflow. Approval of this decision would not make
the technical change provisional and would never authorize deployment.

## 13. Traceability and verification

| Invariant | Owning code | Negative evidence | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `CDR-001` | Five target declarations in the three governed modules | Decorator or method hostile mutations | Exact architecture posture plus focused representation tests | Targeted checker tests and credential-diagnostics module |
| `CDR-002` | Inherited object representation on all five classes | Restore generated repr or expose one protected field | Every protected canary absent from every closed projection item | Credential-diagnostics module |
| `CDR-003` | Same inherited representation used by exception and traceback rendering | Generated repr in a bounded carrier-only frame | Normal and captured-locals synthetic traceback projections contain no canary | Credential-diagnostics module |
| `CDR-004` | Explicit `__eq__` on every target and pinned pytest | Restore generated equality for one class | Real pinned-pytest same-type assertion output contains no canary | Focused pytest-rendering case under locked environment |
| `CDR-005` | Five explicit equality methods and generated dataclass hashes | Omit, duplicate, reorder, or subset one field; accept a subclass; define a hash | Equal clone/equal hash plus one-field inequality for every declared field | Credential-diagnostics equality cases and checker mutations |
| `CDR-006` | `conformance/rewrite_architecture_check.py` exact snapshot rule | Hostile AST mutations for paths, classes, fields, decorator, methods, and equality shape | Governed checker passes only the accepted exact tree | Targeted rewrite architecture tests |
| `CDR-007` | Existing runtime/process-crash/store-loss implementations | Change validation, report, database, or state-machine behavior | Existing focused suites remain green with no runtime diff outside declarations | Existing targeted suites plus base-to-head path/diff audit |
| `CDR-008` | `_Routes`, `_ValidatedInvocation`, and exact five-class checker map | Protect only the three public/input carriers | Derived carriers pass the same projection, equality, and checker rules | Store-loss derivation representation cases and checker tests |

Phase A verification completed before the decision card:

1. package contract checks passed before the RFC-only commits;
2. the draft pull request contained only this RFC at the Phase A head;
3. the exact Phase A head
   `07b51d4516e3ef201212dce9b45f8a590aad983c` received
   [zero-Blocker review](https://github.com/samovers/OFARM2/pull/349#pullrequestreview-5057422093);
4. admitted source run
   [33243805049](https://github.com/samovers/OFARM2/actions/runs/33243805049)
   passed; and
5. trusted publication run
   [33244754972](https://github.com/samovers/OFARM2/actions/runs/33244754972)
   passed before the live decision card and exact task-user approval.

Those Phase A runs are historical design evidence only. They are not reused as
implementation-head acceptance evidence.

Phase B verification, if later approved:

1. package contract check before every commit;
2. focused credential diagnostic representation and equality tests;
3. focused hostile rewrite architecture tests;
4. existing runtime-config, application-runtime, process-crash, store-loss, and
   rewrite-architecture suites selected in proportion to the boundary;
5. complete conformance baseline with no skips, equivalence, and both native
   lanes only after an exact-head zero-Blocker review and valid admission;
6. trusted publication and receipt checks required by repository policy;
7. exact base-to-head path allowlist and card-envelope subset checks;
8. exact-head scope report, cancellation check, and merge-stop recheck; and
9. no deployment, production-composition, or issue-closure action.

Automatically started expensive jobs on an unreviewed head are not acceptance
evidence and will not be monitored, diagnosed, or retried.

## 14. Open decisions and review disposition

### 14.1 Closed design decisions

- The target inventory contains all five exact supported credential-bearing
  dataclasses, including `_Routes` and `_ValidatedInvocation`.
- Representation is class-wide opaque rather than field-by-field partial.
- Equality is explicit, exact-type, and covers every declared field once in
  declaration order.
- Hashing remains generated frozen-dataclass hashing.
- The diagnostic projection is closed and includes only the bounded synthetic
  carrier-only captured-locals frame.
- Actual runner-frame sanitation and explicit serialization are excluded.
- The checker uses exact authenticated source mapping, not name heuristics or
  filesystem rereads.
- The technical allowlist is at most eight paths.
- Version 2 supersedes the unapproved version-1 task draft; only a later
  complete version-2 card can become live.

### 14.2 Current disposition

- **Phase A content Blockers:** zero after exact-head review.
- **Approval:** exact decision version 2 approval recognized on 2026-08-29.
- **Implementation Blockers:** zero known inside the approved boundary.
- **Workflow remaining:** implementation, cheap local checks, exact-head
  zero-Blocker review, fresh admission, hosted baselines and trusted
  publication, scope report, cancellation recheck, and merge-stop recheck.
- **Follow-ups:** four separate items in section 11.4.
- **Preferences:** none outstanding.
- **Production-runtime defects demonstrated by this Phase A review:** none.

There is no remaining material design ambiguity known at this RFC-only head.
If the exact-head review identifies a demonstrated in-boundary Blocker, amend
only the RFC and re-review the affected contract. A change to trust boundary,
authority, invariant, maximum path envelope, or named pull request requires a
new decision version.

### 14.3 Merge stop rule

After approval and implementation, once every invariant passes at the exact
head, required hosted and publication gates pass, scope remains inside the
technical allowlist and card envelope, no cancellation exists, and no
demonstrated Blocker remains, merge the pull request. New ideas, Preferences,
hypothetical risks, and out-of-boundary hardening remain Follow-ups and do not
reopen review.

Phase A is complete and the exact approval is recognized. Phase B may proceed
only inside the approved credential-bearing diagnostic representation boundary.
Nothing in this status transition authorizes production composition,
deployment, certification, current-compliance claims, or issue #192 changes.

## 15. Decision version 3 — post-merge structural-conformance correction

Section 15 is the prospective version-3 amendment. Sections 1 through 14 remain
the historical version-2 design and evidence record. Where current workflow,
pull-request identity, checker enforcement, or status differs, this section is
controlling. It does not withdraw the accepted version-2 carrier behavior.

### 15.1 Historical result, problem, and capability

Pull request #349 merged reviewed head
`ce06ab8b1d8c1f28dd81584945a90c0b1e57092f` as
`a1e2d343b59a5715e07fcb550a459b61dc6541da`. The merge preserved live base
`3d2de4b96a7d99e1e93c2d63b6db2fa46f073564` as its first parent and the
reviewed head as its second parent. Its admitted source run and trusted
publication run succeeded. The approved eight-path boundary was preserved.

The five merged carriers remain opaque on the accepted version-2 diagnostic
surface. No current credential disclosure, governed runtime regression, or
database regression has been demonstrated.

Post-merge review
[#5057956079](https://github.com/samovers/OFARM2/pull/349#pullrequestreview-5057956079)
nevertheless demonstrated one `CDR-006` conformance failure. The checker builds
its member inventory only from direct target-class statements. This valid
target-class source therefore acquires a field-bearing `__repr__` while the
checker returns no forbidden-display violation:

```python
if True:
    __repr__ = lambda self: self.first
```

An import can create the same missed class-namespace binding:

```python
from helper import leaking_repr as __repr__
```

The one independently reviewable version-3 capability is a fail-closed
class-namespace binding analysis for the existing exact five-carrier
architecture rule. Its system-visible outcome is that every statically
expressed class-scope binding or deletion of the forbidden display, hash, and
equality names is rejected before a candidate source tree can receive a
passing architecture verdict.

Delivery issue #352 and draft pull request #354 own this correction. Pull
request #349 is merged and is not recoverable. Delivery issue #350 already owns
that merged implementation and cannot own a second merged implementation pull
request under the current proportional-delivery procedure. Completion of #352
may support a later read-only closure assessment for #350 and #192, but this
decision grants no issue-state authority.

### 15.2 Primary boundary, effects, and authority map

The one primary trust boundary is credential-bearing diagnostic-
representation structural conformance for these five exact classes:

1. `RuntimeConfig`;
2. `ProcessCrashReconciliationSecrets`;
3. `StoreLossRecoverySecrets`;
4. `_Routes`; and
5. `_ValidatedInvocation`.

Permitted effects are limited to:

- replace the shallow special-member scan with one class-namespace binding and
  deletion analysis over the already authenticated detached AST;
- add hostile checker tests for every admitted class-scope binding category
  and for scope boundaries that must not be mistaken for the target class;
- mechanically regenerate the canonical test inventory if collected node IDs
  change; and
- preserve the historical record while adding this current post-merge
  disposition and version-3 design.

The change has these required non-effects:

- no edit to any of the five carrier declarations;
- no representation, formatting, equality, hash, constructor, validation,
  runtime, runner, report, database, or state-machine behavior change;
- no credential creation, access, derivation, ownership, custody, handoff, or
  destruction change;
- no SQL, migration, role, grant, provider, IAM, deployment, production-
  composition, release, certification, or current-compliance effect;
- no new diagnostic or serialization surface;
- no direct filesystem reread, target-module import, or target-code execution
  by the checker; and
- no automatic close, reopen, relabel, or other state change for #192, #350,
  or #352.

| Decision | Sole authority | Rejected alternate or duplicate authority |
| --- | --- | --- |
| Governed source and class inventory | Existing `_CREDENTIAL_DIAGNOSTIC_CARRIERS` exact path/class descriptors | Name heuristic, import-graph inference, test list alone |
| Source bytes and syntax tree | Existing authenticated `PythonSourceSnapshotV1` and its detached AST map | Filesystem reread, imported live module, regex-only scan |
| Forbidden display and hash names | Exact closed set `__repr__`, `__str__`, `__format__`, and `__hash__` | Credential-name heuristic, reviewer-selected subset |
| Equality binding | The one direct synchronous `FunctionDef` named `__eq__` whose body passes the unchanged exact equality-shape rule | Generated equality, nested definition, alias, assignment, deletion, second binding |
| Class-namespace binding and deletion events | Closed syntax-directed event collector in section 15.5 | Direct-body member list, final-name set that loses duplicate events, runtime reflection |
| Architecture verdict | Existing rewrite architecture checker after all exact carrier and event rules pass | Behavioral tests alone, a successful import, design prose |
| Human approval | Exact later task-user approval of the unique live version-3 card naming the existing draft pull request | Version-2 approval, GitHub activity, review, admission, CI, or AI-authored text |

The original target, protected-field, declared-field, decorator, equality, and
hash authorities remain unchanged. Version 3 adds no alternate carrier or
field inventory.

### 15.3 High-risk trust floor and credential custody

#### Protected assets

The protected assets remain the exact password-bearing values reachable
through the five target carriers and the integrity of the architecture verdict
that prevents their generated or custom diagnostic expansion from being
accepted.

The correction checker does not receive live credentials. It receives source
bytes and detached syntax trees. Its diagnostics must name only bounded path,
class, special member, and rule categories; they must not include source
literal values or runtime carrier contents.

#### Trusted components

The correction trusts:

- CPython 3.12.13 parsing and AST node semantics used by the repository
  baseline;
- the existing authenticated source snapshot and detached AST construction;
- the exact `_CREDENTIAL_DIAGNOSTIC_CARRIERS` descriptors;
- the unchanged exact `__eq__` structural validator; and
- the non-malicious checker implementation at the reviewed commit.

#### Untrusted actors and inputs

Within this boundary, future edits to any governed target-class suite are
untrusted. That includes a contributor who places a special-name binding in an
import, assignment, class-scope control-flow branch, loop target,
context-manager target, exception handler, match pattern, assignment
expression, type alias, or nested definition statement.

The source may be syntactically valid while selecting a branch only at class
construction time. The checker cannot treat an apparently false constant
branch as harmless because the source expression or later edit can change.

#### Explicitly excluded attacker capabilities

The exclusions from section 4.4 continue to apply. In particular, arbitrary
class mutation after construction, a compromised interpreter or dependency,
post-snapshot filesystem substitution, debugger or operator compromise, and
arbitrary code already executing in-process are outside this structural source
check.

The event collector governs Python binding and deletion syntax plus the direct
unbounded constructs named below. It does not claim to prove the side effects
of an arbitrary called helper. Direct wildcard import and direct use of
`exec`, `eval`, `locals`, or `vars` in expressions evaluated in the target
class namespace are therefore rejected as unbounded rather than treated as
safe. An indirect namespace mutation hidden inside otherwise ordinary called
code remains outside this syntax-directed claim and cannot be used as passing
acceptance evidence.

#### Primary risk and containment rule

The primary risk is a false-success architecture verdict: a target class binds
a credential-bearing display method or destroys the explicit equality method
through valid class-scope syntax that the checker never observes.

The containment rule is event-based and fail-closed. The checker must collect
every binding and deletion event in the target class execution scope, preserve
duplicates and origin, reject every event for a forbidden display or hash name,
and accept exactly one `__eq__` event only when that event is the direct
synchronous function definition already validated structurally. Unknown or
unbounded class-namespace binding constructs fail rather than silently pass.

#### Custody preservation

Credential custody does not move. The five runtime compositions retain their
existing values and owners. The checker sees authenticated source, not runtime
secrets, creates no credential-bearing artifact, and hands off only bounded
conformance diagnostics and a pass/fail verdict.

### 15.4 Checker ordering and failure model

This correction is stateless and non-transactional. Its complete ordering is:

```text
AUTHENTICATED_SOURCE_SNAPSHOT
  -> DETACHED_AST_RESOLVED_FOR_EXACT_PATH
  -> EXACT_TARGET_CLASS_RESOLVED
  -> CLASS_NAMESPACE_EVENTS_COLLECTED
  -> FORBIDDEN_BINDINGS_AND_DELETIONS_EVALUATED
  -> EXACT_DIRECT_EQUALITY_SHAPE_EVALUATED
  -> PASS_OR_BOUNDED_FAILURE
```

Missing authenticated source, a missing or duplicate class, an unbounded
binding construct, an event-collection ambiguity, or any forbidden event ends
in failure. The equality-shape validator runs against the same detached tree;
there is no second read or time-of-check/time-of-use handoff. No runtime or
database side effect occurs in any state.

### 15.5 Version-3 invariants and closed event taxonomy

#### `CDR3-001` — accepted carrier source remains unchanged

The base-to-head implementation diff contains no change to
`kernel/runtime_config.py`,
`deployment/postgresql/security_audit_process_crash.py`, or
`deployment/postgresql/security_audit_store_loss.py`. The exact five merged
classes must continue to pass the strengthened checker without a runtime edit.

#### `CDR3-002` — class-namespace event collection is closed

For the target class suite, the checker emits ordered binding and deletion
events for the following syntax:

| Syntax | Required event behavior |
| --- | --- |
| `FunctionDef`, `AsyncFunctionDef`, and nested `ClassDef` statements executed in the target class suite | Bind the defined name; preserve whether the accepted `__eq__` node is the direct target-class statement |
| `Import` and `ImportFrom` | Bind each effective alias using Python import binding rules; reject wildcard import as unbounded |
| `Assign`, `AnnAssign`, `AugAssign`, and `NamedExpr` | Bind every class-namespace `Name` target, including starred and tuple/list destructuring |
| `Delete` | Emit a deletion for every class-namespace `Name` target |
| `For` and `AsyncFor` | Bind every loop-target name; inspect the iterator expression; recurse through body and `else` suites |
| `With` and `AsyncWith` | Bind every `as` target; inspect context expressions; recurse through the body |
| `Try` and `TryStar` | Recurse through body, handlers, `else`, and `finally`; bind every exception-handler name |
| `Match` | Bind every capture in `MatchAs`, `MatchStar`, mapping rest, sequence, mapping, class, and OR patterns; inspect subject and guards; recurse through case bodies |
| `TypeAlias` supported by pinned CPython | Bind the alias target; type-parameter scopes do not become target-class scope |
| `Global` or `Nonlocal` naming a governed special member | Reject as ambiguous authority redirection rather than treating it as a safe class binding |

The collector recurses through `if`, `while`, loop, context-manager, exception,
and match suites executed as part of the target class body. It derives whether
`from __future__ import annotations` is active from the same authenticated
module tree. It then applies this mandatory scope-transition table; there is no
optional or generic descent across a scope-forming expression:

| AST form | Expressions inspected as target-class execution | Explicitly excluded nested or deferred execution |
| --- | --- | --- |
| Ordinary class-suite statement | Every value, test, guard, iterator, context expression, and other expression directly evaluated by that statement; child suites recurse under this same table | Any child node assigned a narrower scope below |
| `FunctionDef` or `AsyncFunctionDef` | Decorator expressions, positional defaults, and non-`None` keyword defaults; parameter and return annotations only when future annotations are inactive; then bind the function name | Function body and parameter bindings; annotations when future annotations are active |
| `Lambda` | Positional defaults and non-`None` keyword defaults | Lambda body and parameter bindings |
| `ListComp`, `SetComp`, `DictComp`, or `GeneratorExp` | Only the iterable expression of the leftmost generator | Element, key, value, comprehension targets, filters, and every later generator clause, including its iterable expression |
| Nested `ClassDef` | Decorator, base, and keyword-value expressions evaluated in the enclosing target-class scope; then bind the nested-class name after construction and decoration | Nested class body and its annotation scope |
| `TypeAlias` | Bind the alias target immediately | Lazily evaluated alias value and type-parameter annotation scope |
| `AnnAssign` | Value expression when present; annotation expression only when future annotations are inactive; record the simple-name target under the existing structural field rule | Annotation expression when future annotations are active |

Non-empty PEP 695 `type_params` on a function, async function, or nested class
fail as unsupported/unbounded rather than relying on an unstated annotation-
scope traversal. `TypeAlias` is the one explicitly supported PEP 695 form: its
name is bound immediately, while its value and type parameters are lazy and
are never walked as target-class execution.

Any `NamedExpr` inside a comprehension or generator expression fails as
unsupported/unbounded. Python 3.12 prohibits assignment expressions that
would bind from a comprehension into an enclosing class scope; the checker
does not reinterpret or partially accept such syntax.

Direct calls to `exec`, `eval`, `locals`, or `vars` fail as unbounded only when
they occur in an expression that the table marks as target-class execution.
The same call in a function or lambda body, a comprehension result/filter/later
clause, a nested-class body, a future-deferred annotation, or a lazy type-alias
value is outside the target-class event surface and cannot cause a target-
class violation by itself. Wildcard imports in a governed class suite remain
unbounded.

Every event is retained. A set of final names is insufficient because a valid
direct `__eq__` followed by a hidden rebinding or deletion must not collapse to
one apparently acceptable name.

#### `CDR3-003` — display and hash bindings fail closed

Any binding or deletion event for `__repr__`, `__str__`, `__format__`, or
`__hash__` fails the target class. This applies regardless of control-flow
reachability, order, later rebinding, or later deletion.

#### `CDR3-004` — equality has one accepted authority

There is exactly one `__eq__` binding event. It must be the direct synchronous
`FunctionDef` in the target class body and the same AST node accepted by the
unchanged exact three-step equality validator. A nested definition, async
definition, import, alias, assignment, loop or context target, exception name,
match capture, assignment expression, type alias, second binding, global or
nonlocal declaration, or deletion of `__eq__` fails.

#### `CDR3-005` — nested scopes neither bypass nor overreach

A special-name binding in a class-scope control-flow suite is a target-class
event and fails. Function and lambda defaults, function decorators, eager
annotations, and nested-class decorators, bases, and keyword values are target-
class execution and remain governed. Only the leftmost comprehension iterable
is target-class execution; its targets, result expressions, filters, and later
clauses are in the implicit comprehension scope. Function and lambda bodies,
nested-class bodies, future-deferred annotations, and lazy type-alias values
are also excluded. The same special-name spelling used only in one of those
excluded scopes does not create a target-class event or fail by itself.

#### `CDR3-006` — authenticated inputs and bounded diagnostics are preserved

The strengthened rule consumes only the existing authenticated snapshot and
detached AST map. It does not reread source paths, import target modules,
execute target code, inspect runtime objects, or include source values in a
diagnostic.

All six invariants fail closed. A syntax form that can bind the governed names
in the target namespace but has no defined event handling is a checker failure,
not permission to accept the source.

### 15.6 Production-reachable negative cases

| Invariant | Supported entry, preconditions, and counterexample | Material consequence and required result |
| --- | --- | --- |
| `CDR3-001` | A production operator invokes `kernel.api.create_app()` with accepted production configuration, which constructs `RuntimeConfig`; a contributor's proposed checker fix also edits that already-passing carrier | Runtime configuration behavior could change outside the correction; base-to-head path audit and review reject the carrier edit |
| `CDR3-002` | With an accepted password-bearing production DSN, a contributor puts `exec("__repr__ = lambda self: self.pg_dsn")` in the leftmost iterable of a `RuntimeConfig` class-body comprehension, or in a method default, before `kernel.api.create_app()` constructs it | Those expressions execute in the class namespace and can install a leaking method while whole-comprehension or whole-function skipping passes; the exact transition table visits them, classifies direct `exec` as unbounded, and fails |
| `CDR3-003` | Before `SecurityAuditProcessCrashReconciliationRunner.run()` receives an accepted `ProcessCrashReconciliationSecrets`, a contributor adds `from helper import leaking_repr as __repr__`, or binds `__hash__` through another governed event form | Conninfo can become display-reachable or dataclass hash posture can change while shallow scanning passes; every binding and deletion variant fails before source acceptance |
| `CDR3-004` | Before `SecurityAuditStoreLossRecoveryRunner.run()` receives accepted secrets, a contributor leaves the direct `StoreLossRecoverySecrets.__eq__` definition and adds a class-scope branch that executes `del __eq__` | Dataclass decoration can restore generated field-drilling equality and pinned pytest can display a differing password; the deletion remains a second event and fails |
| `CDR3-005` | The supported store-loss runner derives `_Routes`; paired sources put direct `exec` in the leftmost iterable versus the result expression of a non-empty comprehension, use `__repr__` as the comprehension target, put it inside a nested-class body, and place it in a lazy `TypeAlias` value | Only the leftmost iterable is target-class execution and must fail; the result, target, nested body, and lazy alias value cannot bind `_Routes.__repr__` and must not create a target-class event |
| `CDR3-006` | The supported store-loss validation path derives `_ValidatedInvocation`, and the governed architecture entry receives its authenticated detached AST; a contributor's proposed checker fix rereads the file or imports the target module | Source substitution or target execution could split authority and expose values; authenticated-input hostile tests reject the alternate path before acceptance |

No negative case requires private-field mutation, a fabricated runtime state,
or production credentials. Fictional format-valid canaries and detached hostile
syntax trees are sufficient.

### 15.7 Proposed architecture and smallest complete vertical slice

The checker replaces the current shallow `members` list construction with
one private syntax-directed collector that returns ordered class-namespace
events. An event needs only kind (`bind`, `delete`, or `unbounded`), name when
known, origin node category, and whether it is the exact direct function node.
It is checker-local evidence, not a runtime authority object.

The collector owns traversal. The existing carrier descriptor map continues
to own target and field identity, and `_credential_eq_violations()` continues
to own equality-body structure. `_credential_diagnostic_carrier_violations()`
combines those existing authorities with the event verdict:

1. collect all target-class events;
2. reject unbounded events;
3. reject every display or hash event;
4. require exactly one accepted direct `__eq__` binding and no equality
   deletion or alternate binding; and
5. run the existing exact equality-body validation on that same function node.

Hostile tests use detached source strings and the existing helper. At
minimum they cover the review's nested-`if` and import reproductions, each
event category in `CDR3-002`, duplicate and deletion preservation, wildcard
and direct dynamic-namespace refusal, and continued acceptance of the exact
five authenticated carrier trees. Scope-transition pairs must additionally
prove:

- direct `exec` in a leftmost comprehension iterable fails, while direct
  `exec` in the result expression of an actually iterated comprehension does
  not create a target-class event;
- a comprehension target named `__repr__` remains local to the comprehension;
- direct `exec` in a function or lambda default fails, while the same call in
  its body does not create a target-class event;
- direct `exec` in a nested-class base or decorator expression fails, while
  the same call in the nested-class body does not create an outer event;
- an eager annotation is inspected, while a future-deferred annotation is not;
  and
- a `TypeAlias` name is bound immediately, while its lazy value is not walked
  as target-class execution.

This is the smallest coherent vertical slice because the defect is in one
structural guard. Editing any carrier, adding runtime redaction, reflecting on
live classes, importing target modules, or introducing a general Python symbol
framework would broaden the trust boundary. Adding only an `ImportFrom` case
would leave the demonstrated control-flow family open. A single closed event
collector removes the shallow loop and provides one reviewable authority for
the whole demonstrated gap.

The RFC remains in the same pull request because the exact class-namespace
acceptance model must remain useful after the correction pull request closes.
The checker, hostile tests, RFC, and mechanically required inventory are
companions of one independently testable capability, not separate delivery
units.

### 15.8 Elegance and durable-architecture audit

- **Sources of truth:** one existing carrier descriptor map, one event
  collector for class-namespace semantics, and one existing equality-body
  validator.
- **Authoritative transition points:** authenticated snapshot resolution,
  event collection, and the final carrier violation function; no runtime
  transition is added.
- **Duplicated state:** no second special-name inventory may appear in tests or
  helpers as an independent authority. Tests may assert the exact accepted set
  as conformance evidence.
- **Deletion:** remove the shallow direct-member collection rather than retain
  it beside the new collector.
- **Compatibility surface:** none. No fallback, flag, legacy path, or runtime
  shim is introduced.
- **Rewrite judgment:** a focused replacement of the shallow scan is clearer
  than rewriting the 4,700-line architecture checker or changing the carrier
  design.

### 15.9 Pull-request boundary and complete-slice companions

The version-3 Phase A bootstrap in draft pull request #354 changes this RFC
only. After valid approval, that same pull request may change the four expected
areas listed in the header when needed for the complete slice. Those areas are
scope prediction, not independent approval authority.

The base dependency is merged pull request #349. There is no stacked unmerged
pull request. Pull request #349 review, approval, admission, baselines, and
publication remain historical evidence only and cannot be reused for the new
candidate head.

Reviewers must not require this correction to change a carrier, add a general
redaction framework, sanitize raw runner locals, alter credentials or custody,
change runtime or database behavior, compose production providers, or change
issue state. Evidence that any such change is required stops for separate
Delivery work or a new decision version.

The separate follow-ups remain:

1. protected export-output custody and delivery;
2. production clock, timer, route, provider, and secret-custody evidence under
   parked Tracking Epic #351;
3. complete execution-root and source-capability governance; and
4. read-only tracker closure assessment after bounded corrections.

### 15.10 Traceability and verification

| Invariant | Owning implementation | Hostile or negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `CDR3-001` | No carrier implementation path; base-to-head exclusion | Detect any diff in the three carrier modules | Exact current five carriers pass strengthened rule unchanged | Path diff plus focused checker suite |
| `CDR3-002` | New private class-namespace event collector and mandatory scope-transition dispatch | Parametrized binding taxonomy plus leftmost-comprehension-iterable, function/lambda default, nested-class header, eager-annotation, and unsupported-generic cases | Every supported event and outer execution expression is observed or refused at its exact Python 3.12 scope | Focused `test_rewrite_architecture_check.py` cases |
| `CDR3-003` | Event verdict in `_credential_diagnostic_carrier_violations()` | Bind and delete each display/hash name through direct and nested forms | Every mutation produces bounded violation | Focused hostile checker matrix |
| `CDR3-004` | Event verdict plus existing `_credential_eq_violations()` | Nested, async, imported, assigned, duplicated, and deleted `__eq__` | One direct exact method passes; every alternate event fails | Focused equality-binding cases |
| `CDR3-005` | Collector scope-transition dispatch | Paired leftmost versus result/later comprehension expressions, function/lambda default versus body, nested-class header versus body, eager versus deferred annotation, and alias name versus lazy value | Outer class execution fails when hostile; nested, implicit, or lazy scopes create no target-class event | Paired non-overreach/bypass cases |
| `CDR3-006` | Existing `_check_credential_diagnostic_carriers()` snapshot interface | Missing snapshot/AST and filesystem/import substitution attempts | Detached authenticated trees alone determine verdict | Existing and extended authenticated-input tests |

Phase A permits only mandatory cheap checks. Before each Phase A commit,
`python3 conformance/ofarm_pkg_contract_check.py` must pass under the pinned
CPython 3.12 baseline environment. The RFC-only head receives one exact-head
Phase A review. No expensive hosted baseline is requested, monitored,
diagnosed, or reused for the design-only head.

Approved Phase B verification is:

1. reproduce this traceability and confirm the named draft pull request and
   absence of cancellation;
2. run the package contract check before every commit;
3. run the focused rewrite-architecture hostile tests;
4. run the complete rewrite architecture checker;
5. run Ruff and diff hygiene for changed Python;
6. regenerate the canonical review-baseline inventory only when collected node
   IDs change;
7. verify the three carrier implementation paths have no diff;
8. obtain one zero-Blocker exact-head content review after cheap local checks;
9. only then create fresh exact-head baseline admission and complete required
   hosted baselines, native lanes, trusted publication, and final receipt;
10. post the compact final scope and approval-preservation report; and
11. merge and close Delivery issue #352 only after every gate passes.

### 15.11 Provisional posture

**Technical design:** Not provisional.

The syntax-directed event model is the intended pre-deployment structural
guard for these exact five classes. Evidence requiring a new decision version
would be a Python class-namespace binding form absent from the closed taxonomy,
a need to inspect runtime classes or execute target code, a required edit to a
carrier, or a change to credential custody, runtime behavior, deployment, or
production posture.

The repository approval mechanism remains provisional repository development.
It grants no deployment, release, production access, certification, current-
compliance, or security-waiver authority.

### 15.12 Open decisions, review disposition, and approval stop

The proposed design closes the demonstrated syntax taxonomy and chooses the
event collector over a one-off import check or a broad runtime reflection
mechanism. No material design decision is intentionally left open before
exact-head Phase A review.

Current disposition:

- **Post-merge version-2 conformance Blockers:** one, `CDR-006`, demonstrated
  by review #5057956079;
- **Version-3 Phase A content Blockers:** zero. One scope-transition ambiguity
  was demonstrated at the prior head by
  [review #5058057125](https://github.com/samovers/OFARM2/pull/354#pullrequestreview-5058057125);
  the mandatory transition table and paired evidence closed it in bounded
  [review #5058093561](https://github.com/samovers/OFARM2/pull/354#pullrequestreview-5058093561)
  and confirming
  [review #5058142022](https://github.com/samovers/OFARM2/pull/354#pullrequestreview-5058142022);
- **Version-3 approval:** the exact same-task decision sentence was recognized
  on 2026-08-29;
- **Version-3 implementation review:** pending at the committed implementation
  head;
- **New Follow-ups introduced by version 3:** none;
- **Existing separate Follow-ups:** four in section 15.9;
- **Preferences:** none recorded;
- **Current credential disclosure demonstrated in the merged carriers:** zero;
- **Governed runtime or database regressions demonstrated:** zero; and
- **Version-3 Phase B:** authorized only inside the approved checker, focused
  test, mechanically required inventory, and durable-RFC boundary. Admission,
  hosted baselines, merge, and issue-state changes remain separately gated.

This RFC and the Phase A description bind draft pull request #354. The earlier
version-3 decision card was withdrawn. A replacement complete card was shown
only after the bounded reviews demonstrated zero remaining Blockers, and the
exact later task-user approval is now recognized.

Only the unique complete version-3 decision card in the same Codex task may
request this exact later user message:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-CREDENTIAL-DIAGNOSTIC-REPRESENTATION-001 version 3.
```

Version-2 approval does not satisfy that sentence. The version-3 approval stop
is satisfied for bounded implementation only. No admission, expensive hosted
baseline, merge, issue-state change, deployment, or production-composition
authority follows from that approval.

## 16. Version 4: parenthesized annotated-field conformance

### 16.1 Post-merge disposition and demonstrated defect

Version 3 merged through pull request #354 as commit
`774823336f25e4f9cef79fd7b6f51d1dda3d6745`. Its reviewed implementation head
`8d4d12043f36c80e752ee723b08a132d8d30b3eb` is the merge commit's second
parent, and the reviewed tree was preserved. Source run `33255202798` passed
both 3,713-test baselines, clean-run equivalence, both native verifier lanes,
and the platform lane. Trusted publication run `33256249350` completed and
sealed receipt artifact `9715904610`.

The version-3 ordered namespace-event collector closes the demonstrated import
and class-suite-control-flow special-member bypass. Its event ordering,
definition-time scope transitions, direct synchronous `__eq__` identity, and
authenticated detached-AST boundary remain accepted.

Post-merge
[review #5058662084](https://github.com/samovers/OFARM2/pull/354#pullrequestreview-5058662084)
demonstrates one narrower false-success verdict. The field inventory and the
collector both treat every direct `AnnAssign` with an `ast.Name` target as a
real annotated field/name event without reading `AnnAssign.simple`. CPython
3.12 sets `simple == 0` for a parenthesized name. That name is not placed in
the class `__annotations__` mapping and is not a dataclass field declaration.

Replacing one governed declaration such as `first: str` with `(first): str`
therefore leaves the checker's apparent name tuple unchanged while the actual
dataclass constructor, slots, generated hash inventory, and explicit equality
inputs no longer agree. This is one structural-conformance Blocker, not a
demonstrated credential disclosure in the five current carriers and not a
governed runtime or database regression.

The same review records one repository-currentness Follow-up: the historical
version-3 section still describes its then-live draft, review, admission, and
merge gates. This section appends the completed disposition rather than
rewriting that historical Phase A and pre-merge record.

Pull request #354 and Delivery issue #352 remain completed and are not
recoverable. Delivery issue #357 owns the new correction. Tracking Epic #192
and Delivery issue #350 remain open and receive no state authority from this
decision.

Initial version-4 exact-head review #5058954640 accepted the parenthesized-target
transition but did not test dataclass pseudo-fields or defaults. Later exact-head
[review #5059132827](https://github.com/samovers/OFARM2/pull/358#pullrequestreview-5059132827)
supersedes that disposition and demonstrates one in-boundary design Blocker:
`simple == 1` establishes a class `__annotations__` key, while `ClassVar`,
`InitVar`, `KW_ONLY`, a default, or `field()` options can retain that key and
change fields, slots, constructor, equality inputs, or generated hashing. This
amended contract pins the complete approved direct declaration shape without
executing annotations or resolving arbitrary types.

Amended review #5059157348 verified those direct declaration rules, but later
exact-head
[review #5059215166](https://github.com/samovers/OFARM2/pull/358#pullrequestreview-5059215166)
supersedes its zero-Blocker disposition. The direct projection can still match
the descriptor while the existing recursive collector observes a nested
`AnnAssign(Name(...), simple=1)` for an additional dataclass field. The final
verdict constrained only descriptor-owned names and did not reject that extra
node. This second amendment adds node-identity and multiplicity closure over the
collector's existing target-class execution scope; it adds no walk, resolver,
or authority.

### 16.2 Decision, capability, and primary trust boundary

The proposed decision is
`ISSUE192-SECURITY-AUDIT-CREDENTIAL-DIAGNOSTIC-REPRESENTATION-001`, version 4.
It binds Delivery issue #357 and draft pull request #358, created from branch
`agent/357-parenthesized-annotated-field-phase-a`.

The one independently reviewable capability is a closed direct-declaration
shape inside the existing five-carrier structural guard. A governed field must
be one direct `AnnAssign` with the expected name, `simple == 1`, the exact
approved annotation AST, no value, and no other class-namespace binding for that
name. Every collected `AnnAssign(Name(...), simple=1)` node in target-class
execution scope must be the identical node of one approved direct declaration,
with equal multiplicity. A parenthesized or other non-simple annotated target is
never counted as a field and follows its actual assignment and
expression-evaluation semantics.

The primary trust boundary is credential-bearing diagnostic-representation
structural conformance for the exact direct annotated-field inventory and
class-namespace events of:

1. `RuntimeConfig`;
2. `ProcessCrashReconciliationSecrets`;
3. `StoreLossRecoverySecrets`;
4. `_Routes`; and
5. `_ValidatedInvocation`.

The primary risk is a false-success architecture verdict for source whose
spelling appears to preserve the declared fields while CPython and dataclasses
construct a different class. Parentheses can suppress the `__annotations__`
entry. `ClassVar`, `InitVar`, and `KW_ONLY` can preserve a simple annotation key
while changing field identity. A plain default, `field()` option, or separate
class-body binding can alter constructor or hash posture while preserving the
same annotated name. A nested simple annotation can add a field outside a
direct-only projection. The containment rule therefore combines the exact
approved declaration map, identity closure over every collected simple
declaration node, the closed `simple == 0` execution transition, and the
existing ordered namespace events.

Protected assets are password-bearing DSNs and other admitted secret values
reachable through the five carriers, plus the integrity of the structural
verdict that guards their representation, equality, and hash posture.

Trusted components are CPython 3.12.13 parser/compiler semantics, the existing
authenticated `PythonSourceSnapshotV1`, the detached AST map, the exact ordered
declaration shapes in `_CREDENTIAL_DIAGNOSTIC_CARRIERS`, and the accepted
version-3 namespace-event and equality-body authorities.

Untrusted input is any future edit to a governed target-class suite, including
parenthesized names, pseudo-field annotations, values/defaults, direct or
control-flow rebindings, explicit `__annotations__` access, and dynamic
expressions in annotated assignment values, targets, or annotations. Excluded
attacker capabilities remain a compromised interpreter or dependency,
module-level annotation-name or decorator substitution outside the governed
class suite, post-snapshot source substitution, arbitrary code already
executing in process, debugger/operator compromise, and post-construction
runtime class mutation. Module-level name authority remains in the separate
execution-root/source-capability governance boundary; this decision makes no
claim that syntax alone resolves arbitrary annotation aliases.

### 16.3 Permitted effects, non-effects, and authority map

Permitted effects are:

- extend each existing carrier descriptor with the exact ordered field name and
  annotation-AST shape authority;
- replace the name-only field projection with an exact direct-declaration
  projection that includes `simple`, annotation shape, and value absence;
- refine the `AnnAssign` branch of the accepted namespace collector, require
  exactly one approved declaration event for each governed field, and refuse
  explicit `__annotations__` access in evaluated target-class scope;
- require the tuple of all collected simple annotated-name nodes to equal the
  approved direct declaration-node tuple by identity, order, and multiplicity;
- add focused hostile and paired non-overreach tests for the closed transition,
  pseudo-fields, defaults/options, rebindings, annotation-map mutation, and
  nested extra or duplicate simple declarations;
- regenerate the canonical review-baseline test inventory only for new
  collected node IDs; and
- append the durable merge, defect, correction, and final-disposition record to
  this RFC.

Non-effects and non-goals are:

- no edit to any of the five carrier implementation modules;
- no representation, equality, hash, constructor, validation, credential
  creation, access, derivation, ownership, custody, handoff, or destruction
  change;
- no target import or execution, runtime reflection, direct filesystem reread,
  broad symbol table, general dataclass framework, module-level name resolver,
  or annotation-type resolution;
- no SQL, migration, role, grant, provider, IAM, production composition,
  deployment, release, certification, current-compliance, or security-waiver
  effect; and
- no close, reopen, relabel, or other state change for #192 or #350.

| Decision | Sole authority | Rejected alternate |
| --- | --- | --- |
| Governed carriers and approved declaration tuples | Exact ordered `(field name, annotation AST shape)` entries in `_CREDENTIAL_DIAGNOSTIC_CARRIERS`; every entry also requires `simple == 1` and no value | Name-only tuple, inferred runtime fields, tests alone |
| Source and syntax tree | Existing authenticated snapshot and detached AST map | Filesystem reread, target import, runtime class reflection |
| Annotation-key classification | CPython AST: direct `AnnAssign`, `ast.Name` target, `simple == 1` | `ast.Name` alone, parentheses-insensitive text |
| Complete approved field declarations | Exact ordered descriptor entries, matching direct simple-name `AnnAssign` nodes with exact annotation AST and absent values, identity/multiplicity equality with every collected simple declaration node, per-name event uniqueness, and no explicit annotation-map access | Direct projection alone, name-set comparison, annotation resolution, dataclass execution |
| Non-simple execution semantics | `simple == 0`, value presence, target shape, and future-annotation posture under the closed table below | Generic `ast.walk()`, treating every target as a bind, ignoring evaluated expressions |
| Special-member and equality verdicts | Accepted version-3 ordered events and exact equality-body validator | New duplicate member scan or final-name set |
| Human approval | Exact later task-user approval of the unique version-4 card naming the new draft PR | Version-3 approval, review, GitHub activity, CI, or AI text |

The descriptor must encode the following complete ordered declaration map. The
readable annotation spellings below identify exact Python 3.12 AST expressions;
the implementation compares the location-free `ast.dump(...,
include_attributes=False)` shape committed in the descriptor, not source text.
Every entry requires `simple == 1` and `value is None`.

- `RuntimeConfig`, in order:
  1. `mode: RuntimeMode`;
  2. `deployment_image_digest: str`;
  3. `oidc_issuer: str`;
  4. `oidc_audience: str`;
  5. `oidc_jwks_url: str`;
  6. `pg_dsn: str`;
  7. `tenant_readiness_pg_dsn: str`;
  8. `security_audit_readiness_pg_dsn: str`;
  9. `security_audit_authentication_pg_dsn: str`;
  10. `security_audit_request_router_pg_dsn: str`;
  11. `security_audit_control_pg_dsn: str`;
  12. `correlation_hmac_kms_key_resource: str`;
  13. `tenant_capability_kid: str`;
  14. `signing_evidence_receipt_path: Path`; and
  15. `signing_evidence_observer_public_key: bytes`.
- `ProcessCrashReconciliationSecrets`, in order:
  1. `control_conninfo: str`.
- `StoreLossRecoverySecrets`, in order:
  1. `admin_dsn: str`;
  2. `migrator_dsn: str`;
  3. `control_dsn: str`; and
  4. `login_passwords: tuple[tuple[str, str], ...]`.
- `_Routes`, in order:
  1. `admin_long: str`;
  2. `admin_short: str`;
  3. `admin_target_short: str`;
  4. `migrator_long: str`; and
  5. `control_short: str`.
- `_ValidatedInvocation`, in order:
  1. `request: StoreLossRecoveryRequest`;
  2. `routes: _Routes`; and
  3. `login_passwords: tuple[tuple[str, str], ...]`.

Field names used by protected-field checks, exact equality tuples, and generated
hash posture are derived from this one ordered declaration authority. A second
name-only descriptor is forbidden. The annotation AST is compared structurally
but never evaluated, imported, reflected on, or included in a diagnostic.

### 16.4 Mandatory CPython 3.12 `AnnAssign` transition

The collector must follow this table. “Eager annotation” means the annotation
expression is inspected only when `from __future__ import annotations` is not
active. Future-deferred annotation text is not traversed as target-class
execution.

| Parsed shape | Annotation-key candidate | Evaluated target-class surface and order | Namespace event |
| --- | --- | --- | --- |
| `simple == 1`, no value | Include; approved only when name and annotation match the descriptor | Eager annotation only | One governed annotated-name `bind` event |
| `simple == 1`, value present | Include as an annotation key but reject as an approved declaration | Value, name assignment, eager annotation | One governed annotated-name `bind` event |
| `simple == 0`, parenthesized `ast.Name`, no value | Exclude | Eager annotation only; the store-context name is not evaluated | No name event |
| `simple == 0`, parenthesized `ast.Name`, value present | Exclude | Value, ordinary name assignment, eager annotation | One ordinary assignment `bind` event |
| `simple == 0`, attribute target, no value | Exclude | Target base, then eager annotation | No class-name event |
| `simple == 0`, attribute target, value present | Exclude | Value, target base and assignment, eager annotation | No class-name event; attribute name is not a class binding |
| `simple == 0`, subscript target, no value | Exclude | Target base and index/slice, then eager annotation | No class-name event |
| `simple == 0`, subscript target, value present | Exclude | Value, target base and index/slice and assignment, eager annotation | No class-name event |

For `simple == 1`, CPython's parser supplies an `ast.Name` target. Any detached
AST combination outside `simple in {0, 1}`, or `simple == 1` with a non-name
target, is unsupported and produces one bounded `unbounded` event rather than
silent acceptance.

The event abstraction intentionally records a simple field declaration as a
governed name event even when it has no right-hand side and therefore creates
no ordinary class attribute before dataclass transformation. That event means
“declared in the class annotation namespace,” not “ordinary `STORE_NAME` was
executed.” The two meanings must not be conflated for `simple == 0`.

Direct dynamic-namespace calls remain refused only when they occur in an
expression the table marks as target-class execution. No source value or
annotation value may enter a diagnostic.

The table describes CPython syntax and execution, not sufficient dataclass-field
identity. The exact declaration verdict separately requires the approved
annotation shape, absent value, one matching declaration event, no other bind or
delete event for the governed field name, and no explicit `__annotations__`
reference in evaluated target-class scope. It also requires every collected
simple annotated-name node to be one approved direct declaration node. This
rejects an inline default, a separate assignment that leaves a class attribute
for dataclass processing, and an additional field under class-suite control
flow.

### 16.5 Proposed checker architecture

The name-only `_top_level_class_fields()` projection is replaced by one direct
declaration projection. One pass over the target class's direct statements
retains every `AnnAssign` with an `ast.Name` target and `simple == 1` in source
order and records its name, location-free annotation AST shape, value-absence
posture, and node identity. The result is compared with the descriptor's
complete ordered map. It returns `None` for a missing or duplicated top-level
class. It does not filter a value-bearing or duplicate simple declaration before
comparison, because that could hide an invalid default behind a later
declaration. A `simple == 0` name is excluded from this projection and handled
by the namespace-event transition.

The existing `_CredentialNamespaceCollector` remains the only namespace-event
authority. Its `AnnAssign` handling becomes one explicit dispatch:

1. validate the parser shape and `simple` value;
2. when a value exists, inspect it first;
3. inspect evaluated target components;
4. emit target-name assignment events only for a simple declaration or a
   non-simple target with an actual value;
5. inspect the annotation last only in eager-annotation posture; and
6. emit no target-name event for a value-less non-simple annotation.

After collection, the verdict derives
`collected_simple_declaration_nodes` from `bind` events whose node is
`AnnAssign(Name(...), simple=1)`. It requires the resulting ordered tuple to
equal `approved_direct_declaration_nodes` from the successful descriptor
projection. Equality is by AST node identity and multiplicity, not by name or
shape alone. An extra simple annotation inside `if`, `while`, `for`, `with`,
`try`, `match`, or another accepted target-class control-flow suite therefore
fails. Function, lambda, comprehension, lazy-alias, and nested-class bodies
remain excluded under the accepted version-3 scope rules.

For every descriptor entry, the carrier verdict requires exactly one `bind`
event whose node is the matching approved direct `AnnAssign`, and no other
`bind` or `delete` event for that field name. A separate assignment, import,
definition, control-flow binding, value-bearing parenthesized assignment, or
later deletion therefore cannot supply or alter a dataclass default while the
approved annotation remains visible.

`__annotations__` is a reserved class-namespace authority. Any explicit bind or
delete event for that name is rejected. The existing bounded expression helper
also emits a generic refusal event when an evaluated target-class expression or
target component reads `ast.Name("__annotations__")`; this covers subscript,
attribute-call, and alias-mediated mutation without traversing lazy or
future-deferred annotation scope. Implicit CPython annotation-map updates from
the approved declarations contain no explicit such AST name and remain allowed.

The implementation must reuse the collector's existing bounded expression,
target-expression, target-name, and event helpers. Identity closure is one
filter over the already-collected event tuple and must not add a second AST walk,
execute the fictional class, import a governed module, parse annotations as
trusted runtime values, or infer runtime dataclass fields. Expected
annotation shapes are committed constants, and observed shapes are compared
only in memory. The existing special-member verdict and exact `__eq__` body
validator remain unchanged.

### 16.6 Falsifiable invariants

- `CDR4-001`: the exact five carrier implementation modules have no base-to-
  head diff and continue to pass.
- `CDR4-002`: the direct declaration projection equals the descriptor's complete
  ordered `(field name, annotation AST shape)` map, and every matching statement
  is `AnnAssign(Name(...), simple=1)` with no value. Protected fields and exact
  equality names are derived from that same map. Every simple annotated-name
  node collected in target-class execution scope is identical to one approved
  direct node, with the same order and multiplicity.
- `CDR4-003`: a parenthesized annotation without a value creates no field and
  no namespace-name event; with a value it creates an ordinary assignment
  event but still no field. Paired display/hash and `__eq__` names preserve
  their distinct existing verdicts.
- `CDR4-004`: attribute and subscript target components, values, and eager
  annotations are inspected in the table's execution order without treating
  attribute names as class bindings or traversing future-deferred annotations.
- `CDR4-005`: replacing an approved declaration with a parenthesized name,
  `ClassVar`, `InitVar`, `KW_ONLY`, a plain default, or a `field()` option fails
  before equality or hash posture can be accepted. Each governed name has
  exactly one approved declaration event, no other bind/delete event, and no
  explicit target-class `__annotations__` access. An extra or duplicate simple
  declaration inside class-suite control flow fails node-identity closure.
- `CDR4-006`: version-3 import/control-flow special-member coverage,
  authenticated detached-AST inputs, exact equality identity/body validation,
  and bounded diagnostics remain unchanged.
- `CDR4-007`: the durable RFC records the #354 completion, #5058662084 finding,
  and #5059132827 and #5059215166 Phase A amendments without rewriting
  historical Phase A or claiming production readiness.

### 16.7 Production-reachable negative cases

| Invariant | Counterexample and required result |
| --- | --- |
| `CDR4-001` | A proposed correction also edits `RuntimeConfig` or either security-audit runner carrier; path audit rejects that expansion. |
| `CDR4-002` | Fictional detached source replaces `first: str` with `(first): str`, `first: bytes`, or `first: str = value`; the exact ordered declaration projection differs and is rejected. Source retaining the exact direct map but adding `if True: extra: str` produces a collected node outside the approved direct-node tuple and is rejected. |
| `CDR4-003` | `(__repr__): object` and `(__eq__): object` produce no false extra event, while the corresponding value-bearing forms produce ordinary binding events and are refused by the existing display/hash or exact-equality verdict. |
| `CDR4-004` | A direct dynamic-namespace call in a subscript index or eager annotation is refused; the same spelling in a future-deferred annotation is not treated as executed. |
| `CDR4-005` | The fictional carrier retains the old equality tuple but uses `ClassVar[str]`, `InitVar[str]`, `KW_ONLY`, a plain default, `field(init=False)`, `field(hash=False)`, or `field(kw_only=True)`; declaration comparison rejects every form. An otherwise exact declaration plus `first = value`, `(first): str = value`, `del first`, explicit `__annotations__` mutation, `if True: extra: str`, or nested `first: str` is rejected by event uniqueness, the reserved-namespace rule, or collected-node identity closure. |
| `CDR4-006` | A proposed fix rereads source, imports a carrier, replaces ordered events, or changes equality-body acceptance; focused boundary tests reject it. |
| `CDR4-007` | The RFC omits the #354 completion or either superseding Phase A blocker/amendment from #5059132827 and #5059215166; documentation review rejects the incomplete disposition. |

The negative cases use fictional format-true syntax and the already-supported
production reachability of the five carriers. They require no production
credential, private-field mutation, fabricated runtime state, or carrier-code
edit.

### 16.8 Traceability and verification

| Invariant | Owning change | Focused evidence | Smallest verification |
| --- | --- | --- | --- |
| `CDR4-001` | Base-to-head path exclusion | Exact carrier path diff | Diff audit plus standalone architecture check |
| `CDR4-002` | Ordered declaration descriptors, one direct projection, and identity closure over collected simple declaration nodes | Exact names/annotation ASTs/no-value posture plus nested extra and nested duplicate forms | Descriptor assertion, focused projection tests, and collected-node tuple equality tests |
| `CDR4-003` | Collector `AnnAssign` dispatch | Parenthesized name with and without value for display/hash and `__eq__` | Event and both existing verdict tests |
| `CDR4-004` | Existing expression/target helpers under the new dispatch | Attribute/subscript, eager/future annotation, value-order pairs | Paired scope tests under CPython 3.12.13 |
| `CDR4-005` | Exact declaration, collected-node identity closure, per-field event uniqueness, and reserved `__annotations__` handling | Pseudo-fields, defaults/options, separate rebindings/deletes, annotation-map mutation, and nested extra/duplicate declarations | Hostile mutation matrix under eager and future annotations |
| `CDR4-006` | Unchanged snapshot interface and verdict consumers | Missing AST, alternate source, version-3 regression subset | Focused and complete rewrite-architecture module |
| `CDR4-007` | RFC section 16 and current front matter | Exact merge, review, amendment, and evidence references plus claim audit | Documentation diff review |

Phase A changes only this RFC and the draft pull-request description. No
expensive hosted baseline is permitted for a design-only head.

After valid approval, Phase B cheap verification is:

1. mandatory package contract under pinned CPython 3.12.13 before commit;
2. the focused `AnnAssign.simple`, exact declaration-shape, collected-node
   identity, field-event, and reserved-annotation-map matrix;
3. the complete `kernel/tests/test_rewrite_architecture_check.py` module;
4. the standalone rewrite architecture checker;
5. repository-pinned Ruff for changed Python paths;
6. canonical inventory regeneration only for new collected node IDs;
7. diff hygiene and zero diff for the three governed carrier source paths; and
8. one exact-head implementation review with zero demonstrated Blockers.

Only after that review may a fresh exact-head admission trigger the required
hosted baselines, native lanes, separate trusted publication, and final
receipt. No version-3 check, admission, baseline, publication, or receipt is
reused.

### 16.9 Expected complete-slice paths and separation

Expected paths are scope predictions, not approval authority:

1. `docs/rfcs/OFARM_Security_Audit_Credential_Diagnostic_Representation_RFC_v0_1.md`;
2. `conformance/rewrite_architecture_check.py`;
3. `kernel/tests/test_rewrite_architecture_check.py`; and
4. `conformance/review_baseline_test_inventory.json`, only when mechanically
   required.

The RFC is the Phase A and durable post-merge companion. The checker change,
focused tests, and mechanically necessary inventory form the smallest complete
Phase B slice. No migration, schema, fixture bridge, compatibility layer,
runtime module, carrier change, or process-only companion pull request is
needed.

If implementation or review requires annotation-type resolution, a general
dataclass model, carrier edits, runtime execution, credential custody, SQL,
database authority, provider evidence, deployment, or another issue-state
change, stop before editing and define separate Delivery work or a new decision
version as required.

The existing separate boundaries remain unchanged:

1. protected export-output custody and delivery;
2. production clock, timer, route, provider, and secret-custody evidence under
   parked Tracking Epic #351;
3. complete execution-root and source-capability governance; and
4. read-only tracker closure assessment after bounded corrections.

### 16.10 Failure, rollback, and provisional posture

The checker fails closed for unsupported `AnnAssign` parser shapes. All
diagnostics remain generic and bounded: class identity and invariant category
only, never source text, target values, annotations, credentials, or exception
contents.

There is no durability migration or irreversible effect. Before merge, rollback
is branch abandonment. After merge, a demonstrated regression requires new
Delivery work; it does not make #354 recoverable. Reverting the future checker
commit would restore the known false-success defect and is not an accepted
security rollback.

The technical design is not provisional. Evidence requiring redesign is a
CPython 3.12 execution result contradicting the mandatory table or approved
declaration map, inability to close field-name rebinding without a broader
namespace model, a need to resolve module-level annotation aliases, a need to
execute or reflect on target classes, or a required change to a carrier,
credential custody, runtime, deployment, or production posture.

Repository approval remains a provisional development procedure. Neither the
decision nor any later merge authorizes deployment, release, current/default
promotion, production access, certification, current compliance, or a security
waiver. Production composition remains unauthorized and non-deployable.

### 16.11 Phase A disposition and approval stop

Current amended design disposition after reviews #5059132827 and #5059215166
and before the new exact-head bounded re-review:

- **Phase A content Blockers:** the remaining nested-field blocker is addressed
  by identity and multiplicity closure between collected simple declaration
  nodes and approved direct nodes; closure is pending re-review;
- **New Follow-ups introduced:** zero;
- **Existing separate Follow-ups:** unchanged;
- **Preferences:** pending re-review;
- **Current credential disclosures demonstrated:** zero;
- **Governed runtime or database regressions demonstrated:** zero; and
- **Phase B:** unauthorized.

The only acceptable approval is the entire visible text of a later task-user
message in the same Codex task, after the amended exact-head review demonstrates
zero Blockers and a new unique complete version-4 decision card names the
created draft pull request. Every earlier version-4 card is withdrawn and must
not be used:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-CREDENTIAL-DIAGNOSTIC-REPRESENTATION-001 version 4.
```

Version-3 approval and every review or evidence item from #354 are historical
context only and provide no authority for version 4. Phase A review, GitHub
activity, CI, credentials, tools, or AI-authored text cannot supply approval.
