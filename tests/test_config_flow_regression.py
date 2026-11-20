"""Regression coverage for Home Assistant configuration schemas."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

CONFIG_FLOW = (
    Path(__file__).parents[1]
    / "custom_components"
    / "jg_energy_manager"
    / "config_flow.py"
)


def _function(name: str) -> ast.FunctionDef:
    tree = ast.parse(CONFIG_FLOW.read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_charger_entity_pickers_do_not_apply_domain_filters():
    """Home Assistant must not reject compatible third-party charger entities."""
    function = _function("_charger_schema")
    entity_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_entity"
    ]
    assert len(entity_calls) == 5
    assert all(not call.args and not call.keywords for call in entity_calls)


def test_connected_states_accept_text_and_selector_lists():
    """The validator accepts both current text input and future list selectors."""
    function = _function("_connected_states")
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))

    class Invalid(ValueError):
        pass

    namespace: dict[str, Any] = {
        "Any": Any,
        "cv": SimpleNamespace(string=lambda value: str(value)),
        "vol": SimpleNamespace(Invalid=Invalid),
    }
    exec(compile(module, str(CONFIG_FLOW), "exec"), namespace)
    validate = namespace["_connected_states"]

    assert validate(" B, C, b ") == "B,C"
    assert validate(["B", "C"]) == "B,C"

    try:
        validate(" , ")
    except Invalid:
        pass
    else:
        raise AssertionError("An empty connected-state list must be rejected")


def test_connected_states_field_uses_a_serializable_text_selector():
    """Do not expose the custom normaliser directly in a HA form schema."""
    function = _function("_charger_schema")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    text_selectors = [
        call
        for call in calls
        if isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "selector"
        and call.func.attr == "TextSelector"
    ]
    direct_normalisers = [
        call
        for call in calls
        if isinstance(call.func, ast.Name) and call.func.id == "_connected_states"
    ]

    assert len(text_selectors) == 1
    assert direct_normalisers == []


def test_config_and_options_steps_normalise_connected_states_after_submit():
    """Both flow types keep B,C normalisation without breaking schema serialisation."""
    tree = ast.parse(CONFIG_FLOW.read_text(encoding="utf-8"))
    charger_steps = [
        node
        for parent in tree.body
        if isinstance(parent, ast.ClassDef)
        for node in parent.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_step_charger"
    ]

    assert len(charger_steps) == 2
    for step in charger_steps:
        assert any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_connected_states"
            for call in ast.walk(step)
        )