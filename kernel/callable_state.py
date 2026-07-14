"""Behavior-bearing function state for adjacent retained-call guards.

The RuntimeBundle seal proves the complete process state at governed
boundaries. Point-of-use dispatch also needs a smaller identity-only check so
that replacing a function default, keyword default, closure cell, wrapper, or
function attribute cannot influence one call and restore itself before the
next boundary proof.

The retained state is a flat, deduplicated guard plan. Exact tuples cannot be
mutated after construction, so capture walks them once to discover every
reachable function and mutable dictionary, then holds them strongly. Live
proof checks every unique function, closure cell, and dictionary exactly once
instead of repeatedly walking the same tuple-shaped graph from many roots.
"""
from __future__ import annotations

from types import CellType, FunctionType


_CALLABLE_GUARD_PLAN_V1 = "CALLABLE_GUARD_PLAN_V1"


def capture_callable_state(
        function, active: set[int] | None = None,
) -> tuple[object, ...]:
    """Capture one exact, deduplicated executable-function guard plan.

    ``active`` remains accepted for the internal callers that historically
    shared recursion state. The flat plan has its own strong-reference indexes
    and therefore closes cycles without relying on caller-owned state.
    """
    if type(function) is not FunctionType:
        raise TypeError("retained callable must be an exact Python function")
    if active is not None and type(active) is not set:
        raise TypeError("retained callable active state must be an exact set")

    function_anchors: dict[int, tuple[object, ...]] = {}
    dictionary_anchors: dict[int, tuple[object, ...]] = {}
    closure_anchors: dict[int, tuple[object, ...]] = {}
    retained_tuples: dict[int, tuple] = {}

    def walk_value(value: object) -> None:
        if type(value) is FunctionType:
            walk_function(value)
            return
        if type(value) is tuple:
            retained = retained_tuples.get(id(value))
            if retained is value:
                return
            retained_tuples[id(value)] = value
            for item in value:
                walk_value(item)
            return
        if type(value) is dict:
            retained = dictionary_anchors.get(id(value))
            if retained is not None and retained[0] is value:
                return
            items = tuple(dict.items(value))
            # Install the anchor before descending so a dict that reaches
            # itself through a tuple or function attribute closes exactly.
            dictionary_anchors[id(value)] = (value, items)
            for key, item in items:
                walk_value(key)
                walk_value(item)

    def walk_function(candidate: FunctionType) -> None:
        retained = function_anchors.get(id(candidate))
        if retained is not None and retained[0] is candidate:
            return
        closure = candidate.__closure__
        anchor = (
            candidate,
            candidate.__code__,
            candidate.__defaults__,
            candidate.__kwdefaults__,
            closure,
            candidate.__dict__,
        )
        # Install before walking defaults/closures/attributes. A retained
        # function may refer back to itself through any of those containers.
        function_anchors[id(candidate)] = anchor
        walk_value(candidate.__defaults__)
        walk_value(candidate.__kwdefaults__)
        if closure is not None:
            for cell in closure:
                retained_cell = closure_anchors.get(id(cell))
                if retained_cell is None:
                    retained_cell = (cell, cell.cell_contents)
                    closure_anchors[id(cell)] = retained_cell
                elif (retained_cell[0] is not cell
                      or retained_cell[1] is not cell.cell_contents):
                    raise RuntimeError(
                        "retained closure cell changed during capture")
                _cell, value = retained_cell
                walk_value(value)
        walk_value(candidate.__dict__)

    walk_function(function)
    return (
        _CALLABLE_GUARD_PLAN_V1,
        function,
        tuple(function_anchors.values()),
        tuple(dictionary_anchors.values()),
        tuple(closure_anchors.values()),
    )


def callable_state_matches(
        function, state, active: set[int] | None = None,
) -> bool:
    """Compare live callable state with a self-contained exact guard plan."""
    if active is not None and type(active) is not set:
        return False
    if (type(function) is not FunctionType
            or type(state) is not tuple
            or len(state) != 5
            or state[0] is not _CALLABLE_GUARD_PLAN_V1
            or function is not state[1]
            or type(state[2]) is not tuple
            or not state[2]
            or type(state[2][0]) is not tuple
            or len(state[2][0]) != 6
            or state[2][0][0] is not function
            or type(state[3]) is not tuple
            or type(state[4]) is not tuple):
        return False

    # Validate each unique function exactly once. Defaults and closures retain
    # their exact container identities; reachable functions and dictionaries
    # receive their own independent anchors below.
    for anchor in state[2]:
        if type(anchor) is not tuple or len(anchor) != 6:
            return False
        (candidate, code, defaults, keyword_defaults, closure,
         namespace) = anchor
        if (type(candidate) is not FunctionType
                or candidate.__code__ is not code
                or candidate.__defaults__ is not defaults
                or candidate.__kwdefaults__ is not keyword_defaults
                or candidate.__closure__ is not closure
                or candidate.__dict__ is not namespace):
            return False
        if closure is not None and type(closure) is not tuple:
            return False

    # A dict can mutate in place while preserving its identity. Retain exact
    # insertion order and compare key/value identities without invoking
    # equality or caller-owned mapping behavior.
    try:
        for anchor in state[3]:
            if type(anchor) is not tuple or len(anchor) != 2:
                return False
            mapping, selected_items = anchor
            if (type(mapping) is not dict
                    or type(selected_items) is not tuple
                    or dict.__len__(mapping) != len(selected_items)):
                return False
            for current, selected in zip(dict.items(mapping), selected_items):
                if (type(selected) is not tuple
                        or len(selected) != 2
                        or current[0] is not selected[0]
                        or current[1] is not selected[1]):
                    return False
    except RuntimeError:
        # A concurrent size/order mutation is drift, never a raw guard error.
        return False

    # Closure tuples are immutable and already retained by their function
    # anchors. Shared cells remain mutable, so check each globally unique cell
    # and its exact content identity once.
    try:
        for anchor in state[4]:
            if (type(anchor) is not tuple
                    or len(anchor) != 2
                    or type(anchor[0]) is not CellType
                    or anchor[0].cell_contents is not anchor[1]):
                return False
    except ValueError:
        # Deleting a retained closure cell is executable-state drift.
        return False
    return True
