"""Application-owned principal resolution and control-plane tests."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from kernel.auth_oidc import (
    AuthenticationStartupError,
    OidcError,
    PreBindingOutcome,
    VerifiedOidcIdentity,
)
from kernel.principal_binding import (
    BindingLifecycleHead,
    BindingTransitionRequest,
    BindingVersionCandidate,
    PostgreSQLPrincipalBindingResolver,
    PrincipalBindingAct,
    PrincipalBindingAuthority,
    PrincipalBindingControlError,
    PrincipalBindingControlOutcomeUnknown,
    PrincipalBindingControlPlane,
)


ISSUER = "https://issuer.example.test/tenant"
SUBJECT = "subject-01"
PARTY = "party:operator-01"
DIGEST_A = "sha256:" + "11" * 32
DIGEST_B = "sha256:" + "22" * 32
DIGEST_C = "sha256:" + "33" * 32
DIGEST_D = "sha256:" + "44" * 32


class _Result:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = [] if many is None else many

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _Connection(AbstractContextManager):
    def __init__(self, handler, *, exit_error: BaseException | None = None):
        self.handler = handler
        self.exit_error = exit_error
        self.statements: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.exit_error is not None:
            raise self.exit_error
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        return self.handler(query, params)


class _Factory:
    def __init__(self, connection):
        self.connection = connection

    def __call__(self):
        return self.connection


def _identity():
    return VerifiedOidcIdentity(
        equality_policy="OIDC_EXACT_UTF8_V1",
        issuer=ISSUER,
        subject=SUBJECT,
        claims={},
    )


def _authority():
    now = datetime.now(UTC)
    return PrincipalBindingAuthority(
        equality_policy="OIDC_EXACT_UTF8_V1",
        issuer=ISSUER,
        subject=SUBJECT,
        binding_version_id=uuid4(),
        binding_version_digest=DIGEST_A,
        lifecycle_head_id=uuid4(),
        lifecycle_head_digest=DIGEST_B,
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_C,
        party_ref=PARTY,
        party_record_kind="ofarm.party.v0.1",
        party_record_id=PARTY,
        party_schema_digest=DIGEST_D,
        party_payload_digest="sha256:" + "55" * 32,
        party_state="ACTIVE",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )


def test_resolver_folds_immutable_authority_and_never_reads_projection():
    authority = _authority()
    row = tuple(
        getattr(authority, field)
        for field in authority.__dataclass_fields__
    ) + (True,)

    def handler(query, _params):
        if "check_principal_binding_resolution_dependencies" in query:
            return _Result(one=(None,))
        return _Result(many=[row])

    connection = _Connection(handler)
    resolver = PostgreSQLPrincipalBindingResolver(_Factory(connection))
    resolver.initialize()
    assert resolver.resolve(_identity()) == authority
    sql = "\n".join(query.lower() for query, _ in connection.statements)
    assert "check_principal_binding_resolution_dependencies" in sql
    assert "resolve_principal_binding_authority" in sql
    assert "principal_binding_current" not in sql
    assert "join ofarm.principal_binding" not in sql
    assert "join ofarm.tenant_registry" not in sql
    assert "join ofarm.kernel_record" not in sql


def test_resolver_startup_refuses_unavailable_fixed_database_boundary():
    def handler(query, _params):
        assert (
            "check_principal_binding_resolution_dependencies"
            in query.lower()
        )
        raise PermissionError("simulated unavailable fixed resolver boundary")

    resolver = PostgreSQLPrincipalBindingResolver(
        _Factory(_Connection(handler))
    )
    with pytest.raises(
        AuthenticationStartupError,
        match="principal-binding immutable read path is unavailable",
    ):
        resolver.initialize()


def test_missing_or_ambiguous_binding_fails_closed_with_safe_outcome():
    for rows, outcome in (
        ([], PreBindingOutcome.PRINCIPAL_UNBOUND),
        (
            [tuple(range(18)), tuple(range(18))],
            PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
        ),
    ):

        def handler(query, _params):
            if "check_principal_binding_resolution_dependencies" in query:
                return _Result(one=(None,))
            return _Result(many=rows)

        resolver = PostgreSQLPrincipalBindingResolver(
            _Factory(_Connection(handler))
        )
        resolver.initialize()
        with pytest.raises(OidcError) as raised:
            resolver.resolve(_identity())
        assert raised.value.outcome is outcome
        assert SUBJECT not in str(raised.value)


def test_control_plane_activates_only_through_hardened_functions():
    now = datetime.now(UTC)
    candidate = BindingVersionCandidate(
        binding_version_id=uuid4(),
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_A,
        party_ref=PARTY,
        party_record_kind="ofarm.party.v0.1",
        party_record_id=PARTY,
        party_schema_digest=DIGEST_B,
        party_payload_digest=DIGEST_C,
        party_state="ACTIVE",
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=1),
    )

    def handler(query, _params):
        if "compute_principal_binding_version_digest" in query:
            return _Result(one=(DIGEST_D,))
        if "compute_principal_lifecycle_act_digest" in query:
            return _Result(one=("sha256:" + "66" * 32,))
        if "transition_principal_binding" in query:
            return _Result(one=(None,))
        raise AssertionError(query)

    connection = _Connection(handler)
    controller = PrincipalBindingControlPlane(_Factory(connection))
    receipt = controller.transition(
        BindingTransitionRequest(
            act_kind=PrincipalBindingAct.ACTIVATE,
            issuer=ISSUER,
            subject=SUBJECT,
            expected_head=None,
            effective_at=now,
            decided_at=now,
            accountable_control_ref="control:identity-admin",
            reason="initial-activation",
            candidate=candidate,
        )
    )
    assert receipt.binding_version_id == candidate.binding_version_id
    assert receipt.binding_version_digest == DIGEST_D
    sql = "\n".join(query.lower() for query, _ in connection.statements)
    assert "compute_principal_binding_version_digest" in sql
    assert "compute_principal_lifecycle_act_digest" in sql
    assert "transition_principal_binding" in sql
    assert not any(
        word in sql for word in ("insert into", "update ", "delete from")
    )


def test_control_plane_preserves_generated_act_id_when_commit_is_unknown():
    now = datetime.now(UTC)
    candidate = BindingVersionCandidate(
        binding_version_id=uuid4(),
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_A,
        party_ref=PARTY,
        party_record_kind="ofarm.party.v0.1",
        party_record_id=PARTY,
        party_schema_digest=DIGEST_B,
        party_payload_digest=DIGEST_C,
        party_state="ACTIVE",
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=1),
    )

    def handler(query, _params):
        if "compute_principal_binding_version_digest" in query:
            return _Result(one=(DIGEST_D,))
        if "compute_principal_lifecycle_act_digest" in query:
            return _Result(one=("sha256:" + "66" * 32,))
        if "transition_principal_binding" in query:
            return _Result(one=(None,))
        raise AssertionError(query)

    controller = PrincipalBindingControlPlane(
        _Factory(
            _Connection(
                handler,
                exit_error=ConnectionError("lost commit acknowledgement"),
            )
        )
    )
    with pytest.raises(PrincipalBindingControlOutcomeUnknown) as raised:
        controller.transition(
            BindingTransitionRequest(
                act_kind=PrincipalBindingAct.ACTIVATE,
                issuer=ISSUER,
                subject=SUBJECT,
                expected_head=None,
                effective_at=now,
                decided_at=now,
                accountable_control_ref="control:identity-admin",
                reason="initial-activation",
                candidate=candidate,
            )
        )

    assert type(raised.value.act_id) is UUID
    assert raised.value.act_id.int != 0
    assert str(raised.value.act_id) in str(raised.value)


@pytest.mark.parametrize("naive_bound", ("valid_from", "valid_until"))
def test_control_plane_rejects_naive_candidate_validity_without_database_access(
    naive_bound: str,
) -> None:
    now = datetime.now(UTC)
    candidate = BindingVersionCandidate(
        binding_version_id=uuid4(),
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_A,
        party_ref=PARTY,
        party_record_kind="ofarm.party.v0.1",
        party_record_id=PARTY,
        party_schema_digest=DIGEST_B,
        party_payload_digest=DIGEST_C,
        party_state="ACTIVE",
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=1),
    )
    candidate = replace(
        candidate,
        **{
            naive_bound: (
                candidate.valid_from if naive_bound == "valid_from"
                else candidate.valid_until
            ).replace(tzinfo=None)
        },
    )
    controller = PrincipalBindingControlPlane(
        _Factory(
            _Connection(
                lambda *_: pytest.fail("database must not be called")
            )
        )
    )

    with pytest.raises(
        PrincipalBindingControlError,
        match="principal binding transition refused",
    ):
        controller.transition(
            BindingTransitionRequest(
                act_kind=PrincipalBindingAct.ACTIVATE,
                issuer=ISSUER,
                subject=SUBJECT,
                expected_head=None,
                effective_at=now,
                decided_at=now,
                accountable_control_ref="control:identity-admin",
                reason="initial-activation",
                candidate=candidate,
            )
        )


def test_control_plane_requires_exact_head_and_predecessor_for_supersession():
    now = datetime.now(UTC)
    current_id = uuid4()
    head = BindingLifecycleHead(
        stream_sequence=1,
        act_id=uuid4(),
        act_digest=DIGEST_A,
        current_state="ACTIVE",
        binding_version_id=current_id,
        binding_version_digest=DIGEST_B,
    )
    bad_candidate = BindingVersionCandidate(
        binding_version_id=uuid4(),
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_A,
        party_ref=PARTY,
        party_record_kind="ofarm.party.v0.1",
        party_record_id=PARTY,
        party_schema_digest=DIGEST_B,
        party_payload_digest=DIGEST_C,
        party_state="ACTIVE",
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=1),
        predecessor_version_id=uuid4(),
    )
    controller = PrincipalBindingControlPlane(
        _Factory(
            _Connection(
                lambda *_: pytest.fail("database must not be called")
            )
        )
    )
    with pytest.raises(PrincipalBindingControlError):
        controller.transition(
            BindingTransitionRequest(
                act_kind=PrincipalBindingAct.SUPERSEDE,
                issuer=ISSUER,
                subject=SUBJECT,
                expected_head=head,
                current_binding_version_id=current_id,
                current_binding_version_digest=DIGEST_B,
                candidate=bad_candidate,
                effective_at=now,
                decided_at=now,
                accountable_control_ref="control:identity-admin",
                reason="replacement",
            )
        )
