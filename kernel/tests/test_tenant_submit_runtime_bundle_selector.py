"""Submit verifier mechanics. The compatible package evidence here exists only in tests."""
from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import psycopg
import pytest

from kernel import tenant_submit_runtime_bundle_selector as submit
from kernel.runtime_bundle import (
    Canonicalization, ContentPlacement, RuntimeBundle, RuntimeComponent, RuntimeComponentRole,
)
from kernel.tenant_claim_write_guard import SelectedClaimCommand
from kernel.tenant_command_runtime_bundle_selector import CommandRuntimeBundleSelectionRefused
from kernel.tests.test_tenant_command_runtime_bundle_selector import BATCH_ID, TENANT_REF, _Connection


SELECTION = "ofarm.tenant-command-runtime-bundle-selection.submit-operation-claim.v0.1"
COMMAND = (
    "SUBMIT_OPERATION_CLAIM", "ofarm.submission-command.operation-claim.v0.2", "0.2", "sha256:" + "a" * 64,
)
SELECTION_DIGEST = "sha256:" + "b" * 64
CONTRACT_DIGEST = "sha256:" + "c" * 64
SCHEMA_DIGEST = "sha256:" + "d" * 64


def _component(ref, data):
    return RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.REFERENCE_SOURCE, logical_ref=ref,
        canonicalization=Canonicalization.EXACT_BYTES, placement=ContentPlacement.GLOBAL,
        selected_bytes=data,
    )


@pytest.fixture
def package():
    member = _component("test:required-member", b"required content")
    extra = _component("test:extra-member", b"unrelated content")
    return RuntimeBundle.create((member, extra)), member


@pytest.fixture
def evidence(package):
    _, member = package
    required = {
        "role": member.role.value, "identity": member.logical_ref,
        "canonicalization": member.canonicalization.value, "placement": member.placement.value,
        "byteLength": member.byte_length, "contentDigest": member.content_digest, "schemaIdentity": None,
    }
    closure = {
        "semantics": "EXACT_COMMAND_REQUIRED_COMPONENT_SUBSET", "componentCount": 1, "components": [required],
    }
    selection = submit._SelectionBinding(SELECTION, SELECTION_DIGEST, COMMAND, closure)
    rule = submit._IssuedSubmitRule(
        COMMAND, "ASSERT_OPERATION_CLAIM", "EI_OPERATION_ASSERTION_V0_2", "OPERATION_CLAIM_BODY_V0_2",
        "ofarm.protectedeffect.assertionrecord.submit.v0.1", "0.1", CONTRACT_DIGEST,
        "ofarm.assertionrecord.v0.2", SCHEMA_DIGEST,
    )
    return selection, rule


def _recorded_choice(bundle):
    connection = _Connection(
        bundle, selection_sql="SELECT * FROM ofarm.resolve_submit_operation_claim_runtime_bundle_selection()",
    )
    connection.selection_rows = [(
        connection.tenant_id, TENANT_REF, SELECTION, SELECTION_DIGEST,
        COMMAND[0], COMMAND[1], COMMAND[3], BATCH_ID, 4, bundle.digest, 7,
    )]
    return connection


def _resolve(connection):
    return submit._resolve_assert_operation_claim_runtime_bundle(connection, connection.tenant_id)


def _refuses(connection):
    with pytest.raises(CommandRuntimeBundleSelectionRefused) as raised:
        _resolve(connection)
    assert str(raised.value) == "RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE"
    assert raised.value.__cause__ is None
    assert vars(raised.value) == {}


def test_release_unavailable_even_with_an_internally_consistent_record(package):
    bundle, _ = package
    _refuses(_recorded_choice(bundle))


def test_inert_member_is_hashed_but_cannot_change_selected_command(package, evidence, monkeypatch):
    bundle, _ = package
    monkeypatch.setattr(submit, "_admitted_submit_bindings", lambda: evidence)
    connection = _recorded_choice(bundle)
    result = _resolve(connection)
    assert result.tenant_id == connection.tenant_id
    assert result.tenant_ref == TENANT_REF
    assert result.selection_binding_id == SELECTION
    assert result.selection_binding_canonical_digest == SELECTION_DIGEST
    assert (result.command_id, result.command_binding_id, result.command_binding_version,
            result.command_binding_canonical_digest) == COMMAND
    assert result.selection_batch_id == BATCH_ID
    assert (result.selection_knowledge_position, result.selection_knowledge_cut) == (4, 7)
    assert result.runtime_bundle == bundle
    assert result.rule == evidence[1]
    assert result.selected_claim_command == SelectedClaimCommand(
        connection.tenant_id, "ASSERT_OPERATION_CLAIM", bundle.digest,
        "ofarm.protectedeffect.assertionrecord.submit.v0.1", "0.1", CONTRACT_DIGEST,
        "ofarm.assertionrecord.v0.2", SCHEMA_DIGEST,
    )
    with pytest.raises(FrozenInstanceError):
        result.tenant_ref = "test:other-farm"
    assert connection.calls[0] == (connection.selection_sql, ())
    assert [params for _, params in connection.calls[1:]] == [(connection.tenant_id, bundle.digest)] * 3


@pytest.mark.parametrize("field, wrong", (
    (0, "foreign"), (1, ""), (2, "draft-selection"), (3, "sha256:" + "e" * 64),
    (4, "COMMIT_OPERATION_CLAIM_DRAFT"), (5, "draft-binding"), (6, "sha256:" + "e" * 64),
    (7, "bad-batch"), (8, 8), (9, "sha256:" + "e" * 64), (10, 0),
))
def test_each_mismatched_choice_field_refuses(package, evidence, monkeypatch, field, wrong):
    bundle, _ = package
    connection = _recorded_choice(bundle)
    row = list(connection.selection_rows[0])
    row[field] = uuid4() if field == 0 else wrong
    connection.selection_rows = [tuple(row)]
    monkeypatch.setattr(submit, "_admitted_submit_bindings", lambda: evidence)
    _refuses(connection)


@pytest.mark.parametrize("count", (0, 2))
def test_one_committed_row_required(package, evidence, monkeypatch, count):
    connection = _recorded_choice(package[0])
    connection.selection_rows *= count
    monkeypatch.setattr(submit, "_admitted_submit_bindings", lambda: evidence)
    _refuses(connection)


@pytest.mark.parametrize("failure", (psycopg.errors.InsufficientPrivilege, psycopg.errors.UndefinedFunction))
def test_missing_reader_or_execute_permission_is_opaque(package, evidence, monkeypatch, failure):
    connection = _recorded_choice(package[0])
    connection.failure = failure("private database diagnostic")
    monkeypatch.setattr(submit, "_admitted_submit_bindings", lambda: evidence)
    _refuses(connection)


@pytest.mark.parametrize("attribute, wrong", (
    ("action", "RECEIVE_READ_DATA"), ("intent_profile", "different-intent"),
    ("body_profile", "different-body"), ("contract_id", "different-contract"),
    ("contract_version", "0.2"), ("contract_digest", "malformed"),
    ("result_schema", "different-result"), ("result_schema_digest", "malformed"),
))
def test_incompatible_rule_refuses_before_selection(package, evidence, monkeypatch, attribute, wrong):
    selection, rule = evidence
    other = replace(rule, **{attribute: wrong})
    monkeypatch.setattr(submit, "_admitted_submit_bindings", lambda: (selection, other))
    _refuses(_recorded_choice(package[0]))


@pytest.mark.parametrize("index, wrong", (
    (0, "COMMIT_OPERATION_CLAIM_DRAFT"), (1, "different-binding"), (2, "0.1"), (3, "sha256:" + "e" * 64),
))
def test_independently_issued_command_must_match_selection(package, evidence, monkeypatch, index, wrong):
    selection, rule = evidence
    command = list(COMMAND)
    command[index] = wrong
    different_rule = replace(rule, command=tuple(command))
    monkeypatch.setattr(submit, "_admitted_submit_bindings", lambda: (selection, different_rule))
    _refuses(_recorded_choice(package[0]))


def test_valid_digest_for_same_bytes_under_another_identity_refuses(package, evidence, monkeypatch):
    _, member = package
    replacement = _component("test:another-member", member.canonical_bytes)
    connection = _recorded_choice(RuntimeBundle.create((replacement,)))
    monkeypatch.setattr(submit, "_admitted_submit_bindings", lambda: evidence)
    _refuses(connection)


def test_altering_extra_member_under_selected_digest_refuses(package, evidence, monkeypatch):
    connection = _recorded_choice(package[0])
    index = next(i for i, row in enumerate(connection.content_rows) if row[1] == "test:extra-member")
    row = list(connection.content_rows[index])
    row[2] = b"altered extra"
    connection.content_rows[index] = tuple(row)
    monkeypatch.setattr(submit, "_admitted_submit_bindings", lambda: evidence)
    _refuses(connection)
