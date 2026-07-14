"""Behavior-bearing function state for adjacent retained-call guards.

The RuntimeBundle seal proves the complete process state at governed
boundaries.  Point-of-use dispatch also needs a smaller identity-only check so
that replacing a function default, keyword default, closure cell, or wrapper
cannot influence one call and restore itself before the next boundary proof.
"""
from __future__ import annotations

from types import FunctionType


def _capture_value(value, active: set[int]):
    if type(value) is FunctionType:
        marker = id(value)
        if marker in active:
            return ("FUNCTION_REF", value)
        return ("FUNCTION", capture_callable_state(value, active))
    if type(value) is tuple:
        marker = id(value)
        if marker in active:
            return ("TUPLE_REF", value)
        active.add(marker)
        try:
            return (
                "TUPLE", value,
                tuple(_capture_value(item, active) for item in value),
            )
        finally:
            active.remove(marker)
    if type(value) is dict:
        marker = id(value)
        if marker in active:
            return ("DICT_REF", value)
        active.add(marker)
        try:
            return (
                "DICT", value,
                tuple(
                    (_capture_value(key, active),
                     _capture_value(item, active))
                    for key, item in dict.items(value)
                ),
            )
        finally:
            active.remove(marker)
    return ("IDENTITY", value)


def capture_callable_state(function, active: set[int] | None = None):
    """Capture exact executable function state without caller dispatch."""
    if type(function) is not FunctionType:
        raise TypeError("retained callable must be an exact Python function")
    active = set() if active is None else active
    marker = id(function)
    if marker in active:
        return (function, function.__code__, ("FUNCTION_REF", function))
    active.add(marker)
    try:
        closure = function.__closure__
        closure_state = None if closure is None else (
            closure,
            tuple(
                (cell, _capture_value(cell.cell_contents, active))
                for cell in closure
            ),
        )
        return (
            function,
            function.__code__,
            _capture_value(function.__defaults__, active),
            _capture_value(function.__kwdefaults__, active),
            closure_state,
            _capture_value(vars(function), active),
        )
    finally:
        active.remove(marker)


def callable_state_matches(function, state, active: set[int] | None = None) -> bool:
    """Compare retained state with self-contained identity-only recursion."""
    active = set() if active is None else active

    def value_matches(value, value_state) -> bool:
        if type(value_state) is not tuple or not value_state:
            return False
        kind = value_state[0]
        if kind == "IDENTITY":
            return len(value_state) == 2 and value is value_state[1]
        if kind in {"FUNCTION_REF", "TUPLE_REF", "DICT_REF"}:
            return len(value_state) == 2 and value is value_state[1]
        if kind == "FUNCTION":
            return (len(value_state) == 2
                    and function_matches(value, value_state[1]))
        if kind == "TUPLE":
            if (len(value_state) != 3 or type(value) is not tuple
                    or value is not value_state[1]
                    or len(value) != len(value_state[2])):
                return False
            marker = id(value)
            if marker in active:
                return True
            active.add(marker)
            try:
                return all(
                    value_matches(item, item_state)
                    for item, item_state in zip(value, value_state[2])
                )
            finally:
                active.remove(marker)
        if kind == "DICT":
            if (len(value_state) != 3 or type(value) is not dict
                    or value is not value_state[1]
                    or dict.__len__(value) != len(value_state[2])):
                return False
            marker = id(value)
            if marker in active:
                return True
            active.add(marker)
            try:
                return all(
                    value_matches(key, key_state)
                    and value_matches(item, item_state)
                    for (key, item), (key_state, item_state)
                    in zip(dict.items(value), value_state[2])
                )
            finally:
                active.remove(marker)
        return False

    def function_matches(candidate, function_state) -> bool:
        if (type(candidate) is not FunctionType
                or type(function_state) is not tuple
                or len(function_state) not in {3, 6}
                or candidate is not function_state[0]
                or candidate.__code__ is not function_state[1]):
            return False
        if len(function_state) == 3:
            return (type(function_state[2]) is tuple
                    and len(function_state[2]) == 2
                    and function_state[2][0] == "FUNCTION_REF"
                    and function_state[2][1] is candidate)
        marker = id(candidate)
        if marker in active:
            return True
        active.add(marker)
        try:
            closure = candidate.__closure__
            closure_state = function_state[4]
            if closure_state is None:
                closure_matches = closure is None
            else:
                closure_matches = (
                    type(closure) is tuple
                    and closure is closure_state[0]
                    and len(closure) == len(closure_state[1])
                    and all(
                        cell is expected_cell
                        and value_matches(cell.cell_contents, cell_state)
                        for cell, (expected_cell, cell_state)
                        in zip(closure, closure_state[1])
                    )
                )
            return (
                closure_matches
                and value_matches(candidate.__defaults__, function_state[2])
                and value_matches(candidate.__kwdefaults__, function_state[3])
                and value_matches(vars(candidate), function_state[5])
            )
        finally:
            active.remove(marker)

    return function_matches(function, state)
