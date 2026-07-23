"""Read-only composition of verified identities and database authority."""
from __future__ import annotations

from collections.abc import Callable

import psycopg

from deployment.postgresql.tenant_contract import TENANT_CAPABILITY_CONTRACT

from .authentication import VerifiedIdentity
from .principal import (
    AuthenticatedPrincipal,
    PrincipalAuthority,
    PrincipalResolutionError,
    PrincipalResolutionOutcome,
    PrincipalResolutionStartupError,
)


ConnectionFactory = Callable[[], psycopg.Connection[tuple[object, ...]]]
_RUNTIME_API_VERSION = "ofarm.authentication-runtime.v1"


class PrincipalBindingResolver:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        expected_audience: str,
    ) -> None:
        if type(expected_audience) is not str or not expected_audience:
            raise PrincipalResolutionStartupError(
                "principal audience configuration is invalid"
            )
        self._connection_factory = connection_factory
        self._expected_audience = expected_audience
        self._initialized = False

    def initialize(self) -> None:
        try:
            with self._connection_factory() as connection:
                cursor = connection.execute(
                    "SELECT * FROM ofarm.observe_authentication_runtime_contract()"
                )
                row = cursor.fetchone()
                duplicate = cursor.fetchone()
        except psycopg.Error as exc:
            raise PrincipalResolutionStartupError(
                "principal authority initialization failed"
            ) from exc
        if (
            type(row) is not tuple
            or len(row) != 3
            or duplicate is not None
            or row[0] != self._expected_audience
            or row[1] != TENANT_CAPABILITY_CONTRACT.digest
            or row[2] != _RUNTIME_API_VERSION
        ):
            raise PrincipalResolutionStartupError(
                "principal authority contract differs"
            )
        self._initialized = True

    def resolve(self, identity: VerifiedIdentity) -> AuthenticatedPrincipal:
        if not self._initialized:
            raise PrincipalResolutionError(
                PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE
            )
        try:
            with self._connection_factory() as connection:
                cursor = connection.execute(
                    """
                    SELECT *
                    FROM ofarm.resolve_principal_binding_authority(%s, %s, %s)
                    """,
                    (
                        identity.equality_policy,
                        identity.issuer,
                        identity.subject,
                    ),
                )
                row = cursor.fetchone()
                duplicate = cursor.fetchone()
        except psycopg.Error as exc:
            raise PrincipalResolutionError(
                PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE
            ) from exc
        if row is None:
            raise PrincipalResolutionError(
                PrincipalResolutionOutcome.UNRESOLVED
            )
        if type(row) is not tuple or duplicate is not None:
            raise PrincipalResolutionError(
                PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE
            )
        try:
            authority = PrincipalAuthority.from_database_row(row, identity)
        except (TypeError, ValueError) as exc:
            raise PrincipalResolutionError(
                PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE
            ) from exc
        return AuthenticatedPrincipal(identity=identity, authority=authority)
