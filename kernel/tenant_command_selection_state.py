"""Keep one command selection on its owning unit until finalization."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from .tenant_command_runtime_bundle_selector import (
    CommandRuntimeBundleSelectionRefused, TrustedCommandRuntimeBundle,
)
from .tenant_submit_runtime_bundle_selector import TrustedAssertOperationClaimRuntimeBundle

CommandBundle = TypeVar(
    "CommandBundle", TrustedCommandRuntimeBundle, TrustedAssertOperationClaimRuntimeBundle
)


class UnitCommandSelection:
    __slots__ = ("_draft", "_submit", "_selected")

    def __init__(
        self,
        draft: Callable[[], TrustedCommandRuntimeBundle],
        submit: Callable[[], TrustedAssertOperationClaimRuntimeBundle] | None,
    ) -> None:
        self._draft = draft
        self._submit = submit
        self._selected: object = None

    def resolve(
        self, expected: type[CommandBundle], require_selectable: Callable[[], None]
    ) -> CommandBundle:
        require_selectable()
        if type(self._selected) is expected:
            return cast(CommandBundle, self._selected)
        if self._selected is not None:
            raise CommandRuntimeBundleSelectionRefused from None

        # The type reserves this command while reading. Its verified instance
        # then occupies the same slot for the rest of the unit's lifetime.
        self._selected = expected
        read = self._draft if expected is TrustedCommandRuntimeBundle else self._submit
        if read is None:
            raise CommandRuntimeBundleSelectionRefused from None
        selected = read()
        require_selectable()
        if self._selected is not expected:
            raise CommandRuntimeBundleSelectionRefused from None
        if type(selected) is not expected:
            raise RuntimeError("selector result differs")
        self._selected = selected
        return cast(CommandBundle, selected)

    def selected_assertion(self) -> TrustedAssertOperationClaimRuntimeBundle | None:
        if type(self._selected) is TrustedAssertOperationClaimRuntimeBundle:
            return self._selected
        return None
