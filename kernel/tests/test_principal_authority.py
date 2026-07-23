"""Client-side principal mapping and closed control outcomes."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
import pytest

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_CONTRACT,
    TENANT_CAPABILITY_PARTY_RECORD_KIND,
)
from kernel.authentication import VerifiedIdentity
from kernel.principal import (
    PrincipalResolutionError,
    PrincipalResolutionOutcome,
    PrincipalResolutionStartupError,
)
from kernel.principal_control import (
    PrincipalBindingCandidate,
    PrincipalBindingController,
    PrincipalBindingTransitionRequest,
    PrincipalControlError,
    PrincipalControlUnavailable,
    PrincipalTransitionKind,
    TransitionOutcomeUnknown,
    TransitionRefused,
)
from kernel.principal_resolver import PrincipalBindingResolver


ISSUER = "https://issuer.example.test/tenant"
SUBJECT = "subject:Exact-01"
AUDIENCE = (
    "urn:ofarm:tenant-binder:v1:"
    "a58b7238-5019-49e2-9aaf-530287e5a6ee"
)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
IDENTITY = VerifiedIdentity(
    equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
    issuer=ISSUER,
    subject=SUBJECT,
)
NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]]):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class _Transaction:
    def __init__(self, commit_error: Exception | None = None):
        self.commit_error = commit_error

    def __enter__(self):
        return self

    def __exit__(self, exception_type, _exception, _traceback):
        if exception_type is None and self.commit_error is not None:
            raise self.commit_error
        return False


class _Connection:
    def __init__(
        self,
        responses: list[list[tuple[object, ...]]],
        *,
        autocommit: bool = False,
        fail_at: int | None = None,
        failure: Exception | None = None,
        commit_error: Exception | None = None,
    ):
        self.responses = list(responses)
        self.autocommit = autocommit
        self.fail_at = fail_at
        self.failure = failure
        self.commit_error = commit_error
        self.executions: list[tuple[str, tuple[object, ...] | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, _exception_type, _exception, _traceback):
        return False

    def transaction(self):
        return _Transaction(self.commit_error)

    def execute(self, statement: str, parameters=None):
        self.executions.append((statement, parameters))
        if len(self.executions) == self.fail_at:
            assert self.failure is not None
            raise self.failure
        rows = self.responses.pop(0) if self.responses else []
        return _Cursor(rows)


class _Factory:
    def __init__(
        self,
        *connections: _Connection,
        failure: Exception | None = None,
    ):
        self.connections = list(connections)
        self.failure = failure
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return self.connections.pop(0)


def _authority_row(**changes) -> tuple[object, ...]:
    values = [
        OIDC_ISSUER_EQUALITY_POLICY,
        ISSUER,
        SUBJECT,
        uuid4(),
        DIGEST_A,
        uuid4(),
        DIGEST_B,
        uuid4(),
        DIGEST_C,
        "party:Exact-01",
        TENANT_CAPABILITY_PARTY_RECORD_KIND,
        "party:Exact-01",
        DIGEST_A,
        DIGEST_B,
        "ACTIVE",
        NOW - timedelta(days=1),
        NOW + timedelta(days=1),
    ]
    indexes = {
        "issuer": 1,
        "subject": 2,
        "party_record_id": 11,
        "party_state": 14,
        "valid_until": 16,
    }
    for name, value in changes.items():
        values[indexes[name]] = value
    return tuple(values)


def _initialized_resolver(
    resolve_rows: list[tuple[object, ...]],
) -> tuple[PrincipalBindingResolver, _Connection]:
    contract = _Connection(
        [[(AUDIENCE, TENANT_CAPABILITY_CONTRACT.digest,
           "ofarm.authentication-runtime.v1")]]
    )
    resolution = _Connection([resolve_rows])
    resolver = PrincipalBindingResolver(_Factory(contract, resolution))
    resolver.initialize()
    return resolver, resolution


def test_resolver_maps_one_exact_authority_row():
    row = _authority_row()
    resolver, connection = _initialized_resolver([row])

    principal = resolver.resolve(IDENTITY)

    assert resolver.audience == AUDIENCE
    assert principal.identity is IDENTITY
    assert principal.authority.binding_version_id == row[3]
    assert principal.authority.tenant_id == row[7]
    assert principal.authority.party_ref == "party:Exact-01"
    assert connection.executions[0][1] == (
        OIDC_ISSUER_EQUALITY_POLICY,
        ISSUER,
        SUBJECT,
    )


def test_resolver_requires_initialization_without_opening_a_connection():
    factory = _Factory(_Connection([]))
    resolver = PrincipalBindingResolver(factory)

    with pytest.raises(PrincipalResolutionError) as raised:
        resolver.resolve(IDENTITY)

    assert raised.value.outcome is (
        PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE
    )
    assert factory.calls == 0


@pytest.mark.parametrize(
    ("rows", "outcome"),
    [
        ([], PrincipalResolutionOutcome.UNRESOLVED),
        (
            [_authority_row(issuer=ISSUER + "/changed")],
            PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE,
        ),
        (
            [_authority_row(), _authority_row()],
            PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE,
        ),
    ],
)
def test_resolver_exposes_only_closed_resolution_outcomes(rows, outcome):
    resolver, _connection = _initialized_resolver(rows)

    with pytest.raises(PrincipalResolutionError) as raised:
        resolver.resolve(IDENTITY)

    assert raised.value.outcome is outcome


def test_resolver_refuses_a_mismatched_database_contract():
    connection = _Connection(
        [[(AUDIENCE, DIGEST_A, "ofarm.authentication-runtime.v1")]]
    )
    resolver = PrincipalBindingResolver(_Factory(connection))

    with pytest.raises(PrincipalResolutionStartupError):
        resolver.initialize()


def _candidate(
    predecessor: UUID | None = None,
) -> PrincipalBindingCandidate:
    return PrincipalBindingCandidate(
        binding_version_id=uuid4(),
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_A,
        party_ref="party:Exact-01",
        party_record_id="party:Exact-01",
        party_schema_digest=DIGEST_B,
        party_payload_digest=DIGEST_C,
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
        predecessor_version_id=predecessor,
    )


def _request(
    kind: PrincipalTransitionKind = PrincipalTransitionKind.ACTIVATE,
) -> PrincipalBindingTransitionRequest:
    active_id = None
    active_digest = None
    expected_id = None
    expected_digest = None
    sequence = 1
    candidate = _candidate()
    if kind is not PrincipalTransitionKind.ACTIVATE:
        active_id = uuid4()
        active_digest = DIGEST_A
        expected_id = uuid4()
        expected_digest = DIGEST_B
        sequence = 2
        candidate = (
            _candidate(active_id)
            if kind is PrincipalTransitionKind.SUPERSEDE
            else None
        )
    return PrincipalBindingTransitionRequest(
        identity=IDENTITY,
        act_id=uuid4(),
        kind=kind,
        stream_sequence=sequence,
        expected_head_id=expected_id,
        expected_head_digest=expected_digest,
        active_binding_version_id=active_id,
        active_binding_version_digest=active_digest,
        candidate=candidate,
        effective_at=NOW - timedelta(seconds=2),
        decided_at=NOW - timedelta(seconds=1),
        accountable_control_ref="control:identity",
        reason="requested-transition",
    )


def test_activation_maps_digest_and_transition_parameters_exactly():
    request = _request()
    connection = _Connection(
        [[(DIGEST_A,)], [(DIGEST_B,)], [(None,)]]
    )
    result = PrincipalBindingController(_Factory(connection)).transition(request)

    assert result.act_id == request.act_id
    assert result.act_digest == DIGEST_B
    transition_parameters = connection.executions[2][1]
    assert transition_parameters is not None
    assert transition_parameters[:8] == (
        OIDC_ISSUER_EQUALITY_POLICY,
        ISSUER,
        SUBJECT,
        None,
        None,
        request.act_id,
        DIGEST_B,
        "ACTIVATE",
    )
    assert transition_parameters[10:20] == (
        request.candidate.binding_version_id,
        DIGEST_A,
        request.candidate.tenant_id,
        DIGEST_A,
        "party:Exact-01",
        TENANT_CAPABILITY_PARTY_RECORD_KIND,
        "party:Exact-01",
        DIGEST_B,
        DIGEST_C,
        "ACTIVE",
    )


@pytest.mark.parametrize(
    "kind",
    [
        PrincipalTransitionKind.REVOKE,
        PrincipalTransitionKind.EXPIRE,
        PrincipalTransitionKind.SUPERSEDE,
    ],
)
def test_non_initial_transition_mapping_is_closed_by_kind(kind):
    request = _request(kind)
    responses = (
        [[(DIGEST_C,)], [(DIGEST_B,)], [(None,)]]
        if kind is PrincipalTransitionKind.SUPERSEDE
        else [[(DIGEST_B,)], [(None,)]]
    )
    connection = _Connection(responses)

    PrincipalBindingController(_Factory(connection)).transition(request)

    parameters = connection.executions[-1][1]
    assert parameters is not None
    assert parameters[7] == kind.value
    assert parameters[8:10] == (
        request.active_binding_version_id,
        request.active_binding_version_digest,
    )
    if kind is PrincipalTransitionKind.SUPERSEDE:
        assert parameters[10:12] == (
            request.candidate.binding_version_id,
            DIGEST_C,
        )
    else:
        assert parameters[10:23] == (None,) * 13


def test_nil_caller_supplied_act_id_is_refused_before_connection():
    request = _request()
    invalid = replace(request, act_id=UUID(int=0))
    factory = _Factory(_Connection([]))

    with pytest.raises(PrincipalControlError):
        PrincipalBindingController(factory).transition(invalid)

    assert factory.calls == 0


def test_autocommit_connection_is_refused_before_statements():
    connection = _Connection([], autocommit=True)

    with pytest.raises(PrincipalControlError):
        PrincipalBindingController(_Factory(connection)).transition(_request())

    assert connection.executions == []


@pytest.mark.parametrize(
    "commit_error",
    [None, psycopg.OperationalError("commit result lost")],
)
def test_connection_failure_after_transition_submission_is_unknown(
    commit_error,
):
    request = _request()
    connection = _Connection(
        [[(DIGEST_A,)], [(DIGEST_B,)]],
        fail_at=3 if commit_error is None else None,
        failure=psycopg.OperationalError("connection lost"),
        commit_error=commit_error,
    )

    with pytest.raises(TransitionOutcomeUnknown) as raised:
        PrincipalBindingController(_Factory(connection)).transition(request)

    assert raised.value.act_id == request.act_id


def test_connection_failure_before_submission_is_unavailable():
    request = _request()
    connection = _Connection(
        [],
        fail_at=1,
        failure=psycopg.OperationalError("connection lost"),
    )

    with pytest.raises(PrincipalControlUnavailable):
        PrincipalBindingController(_Factory(connection)).transition(request)


def test_database_refusal_after_submission_is_not_reported_as_unknown():
    request = _request()
    connection = _Connection(
        [[(DIGEST_A,)], [(DIGEST_B,)]],
        fail_at=3,
        failure=psycopg.errors.CheckViolation("transition refused"),
    )

    with pytest.raises(TransitionRefused) as raised:
        PrincipalBindingController(_Factory(connection)).transition(request)

    assert raised.value.act_id == request.act_id
