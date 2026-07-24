"""Read-only correlation-HMAC lifecycle posture across PostgreSQL and KMS."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

import psycopg
from google.api_core import exceptions as google_exceptions
from google.cloud import kms_v1
from google.cloud.kms_v1.services.key_management_service import pagers

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT

Connection = psycopg.Connection[tuple[object, ...]]
ConnectionFactory = Callable[[], Connection]
_KNOWN_VERSIONS = SECURITY_AUDIT_CONTRACT.correlation_hmac_known_key_versions
_ACTIVE_VERSION = SECURITY_AUDIT_CONTRACT.correlation_hmac.key_version
_READ_ONLY = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
_OBSERVE = "SELECT * FROM ofarm_security.observe_correlation_hmac_key_retention(%s)"
_PARENT = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"locations/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/"
    r"keyRings/[A-Za-z0-9_-]{1,63}/cryptoKeys/[A-Za-z0-9_-]{1,63}$"
)


class CorrelationHmacVersionDisposition(Enum):
    ACTIVE = "ACTIVE"
    RETIREMENT_REQUIRED = "RETIREMENT_REQUIRED"
    DESTROY_SCHEDULED_OBSERVED = "DESTROY_SCHEDULED_OBSERVED"
    DESTROYED_OBSERVED = "DESTROYED_OBSERVED"


@dataclass(frozen=True, slots=True)
class CorrelationHmacVersionPosture:
    key_version: int
    kms_state: str
    disposition: CorrelationHmacVersionDisposition
    greatest_purge_after: datetime | None


@dataclass(frozen=True, slots=True)
class CorrelationHmacLifecyclePosture:
    versions: tuple[CorrelationHmacVersionPosture, ...]


@dataclass(frozen=True, slots=True)
class _DatabaseVersion:
    key_version: int
    active: bool
    greatest_purge_after: datetime | None


class KmsLifecycleClient(Protocol):
    def list_crypto_key_versions(
        self,
        *,
        request: kms_v1.ListCryptoKeyVersionsRequest,
        retry: None,
        timeout: float,
    ) -> pagers.ListCryptoKeyVersionsPager: ...

    def get_crypto_key_version(
        self,
        *,
        request: kms_v1.GetCryptoKeyVersionRequest,
        retry: None,
        timeout: float,
    ) -> kms_v1.CryptoKeyVersion: ...


class CorrelationHmacLifecycleUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("correlation HMAC lifecycle posture is unavailable")


def _aware_time(value: object) -> datetime | None:
    return value if (
        type(value) is datetime
        and value.tzinfo is not None
        and value.utcoffset() is not None
    ) else None


def _database_versions(factory: ConnectionFactory) -> tuple[_DatabaseVersion, ...]:
    observed = []
    try:
        with factory() as connection:
            if connection.autocommit is not False:
                raise CorrelationHmacLifecycleUnavailable()
            with connection.transaction():
                connection.execute(_READ_ONLY)
                for expected in _KNOWN_VERSIONS:
                    cursor = connection.execute(_OBSERVE, (expected,))
                    row = cursor.fetchone()
                    duplicate = cursor.fetchone()
                    if type(row) is not tuple or len(row) != 3 or duplicate is not None:
                        raise CorrelationHmacLifecycleUnavailable()
                    version, active, purge_after = row
                    if (
                        type(version) is not int
                        or version != expected
                        or type(active) is not bool
                        or (
                            purge_after is not None
                            and _aware_time(purge_after) is None
                        )
                    ):
                        raise CorrelationHmacLifecycleUnavailable()
                    observed.append(_DatabaseVersion(version, active, purge_after))
    except psycopg.Error as exc:
        raise CorrelationHmacLifecycleUnavailable() from exc
    active = tuple(value.key_version for value in observed if value.active)
    if active != (_ACTIVE_VERSION,):
        raise CorrelationHmacLifecycleUnavailable()
    return tuple(observed)


def _resource_version(parent: str, resource: object) -> int | None:
    prefix = parent + "/cryptoKeyVersions/"
    if type(resource) is not str or not resource.startswith(prefix):
        return None
    suffix = resource[len(prefix) :]
    return int(suffix) if re.fullmatch(r"[1-9][0-9]*", suffix) else None


def _listed_versions(
    client: KmsLifecycleClient,
    parent: str,
    timeout: float,
) -> None:
    request = kms_v1.ListCryptoKeyVersionsRequest(
        parent=parent,
        page_size=len(_KNOWN_VERSIONS) + 1,
    )
    try:
        pager = client.list_crypto_key_versions(
            request=request,
            retry=None,
            timeout=timeout,
        )
        response = next(iter(pager.pages))
    except (
        google_exceptions.GoogleAPICallError,
        google_exceptions.RetryError,
        StopIteration,
        TimeoutError,
    ) as exc:
        raise CorrelationHmacLifecycleUnavailable() from exc
    if (
        not isinstance(response, kms_v1.ListCryptoKeyVersionsResponse)
        or response.next_page_token
    ):
        raise CorrelationHmacLifecycleUnavailable()
    versions = tuple(
        _resource_version(parent, value.name)
        if isinstance(value, kms_v1.CryptoKeyVersion)
        else None
        for value in response.crypto_key_versions
    )
    if (
        None in versions
        or len(versions) != len(set(versions))
        or set(versions) != set(_KNOWN_VERSIONS)
    ):
        raise CorrelationHmacLifecycleUnavailable()


def _disposition(
    version: kms_v1.CryptoKeyVersion,
    active: bool,
) -> CorrelationHmacVersionDisposition:
    state = version.state
    states = kms_v1.CryptoKeyVersion.CryptoKeyVersionState
    if active and state == states.ENABLED:
        return CorrelationHmacVersionDisposition.ACTIVE
    inactive = {
        states.ENABLED: CorrelationHmacVersionDisposition.RETIREMENT_REQUIRED,
        states.DISABLED: CorrelationHmacVersionDisposition.RETIREMENT_REQUIRED,
        states.DESTROY_SCHEDULED:
            CorrelationHmacVersionDisposition.DESTROY_SCHEDULED_OBSERVED,
        states.DESTROYED: CorrelationHmacVersionDisposition.DESTROYED_OBSERVED,
    }
    if not active and state in inactive:
        return inactive[state]
    raise CorrelationHmacLifecycleUnavailable()


def _kms_version(
    client: KmsLifecycleClient,
    parent: str,
    database: _DatabaseVersion,
    timeout: float,
) -> CorrelationHmacVersionPosture:
    resource = f"{parent}/cryptoKeyVersions/{database.key_version}"
    try:
        version = client.get_crypto_key_version(
            request=kms_v1.GetCryptoKeyVersionRequest(name=resource),
            retry=None,
            timeout=timeout,
        )
    except (
        google_exceptions.GoogleAPICallError,
        google_exceptions.RetryError,
        TimeoutError,
    ) as exc:
        raise CorrelationHmacLifecycleUnavailable() from exc
    if (
        not isinstance(version, kms_v1.CryptoKeyVersion)
        or version.name != resource
        or version.algorithm
        != kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.HMAC_SHA256
        or version.protection_level != kms_v1.ProtectionLevel.HSM
    ):
        raise CorrelationHmacLifecycleUnavailable()
    disposition = _disposition(version, database.active)
    return CorrelationHmacVersionPosture(
        database.key_version,
        version.state.name,
        disposition,
        database.greatest_purge_after,
    )


class CorrelationHmacLifecycleObserver:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        kms_client: KmsLifecycleClient,
        kms_parent_resource: str,
        *,
        rpc_timeout_seconds: float = 5,
    ) -> None:
        if (
            type(kms_parent_resource) is not str
            or _PARENT.fullmatch(kms_parent_resource) is None
            or type(rpc_timeout_seconds) not in (int, float)
            or isinstance(rpc_timeout_seconds, bool)
            or not 0 < rpc_timeout_seconds <= 30
            or _ACTIVE_VERSION is None
        ):
            raise CorrelationHmacLifecycleUnavailable()
        self._connection_factory = connection_factory
        self._kms_client = kms_client
        self._parent = kms_parent_resource
        self._timeout = float(rpc_timeout_seconds)

    def current(self) -> CorrelationHmacLifecyclePosture:
        database = _database_versions(self._connection_factory)
        _listed_versions(self._kms_client, self._parent, self._timeout)
        versions = tuple(
            _kms_version(self._kms_client, self._parent, value, self._timeout)
            for value in database
        )
        return CorrelationHmacLifecyclePosture(versions)
