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


def _compiled_function(name: str, namespace: dict[str, Any]):
    function = _function(name)
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(CONFIG_FLOW), "exec"), namespace)
    return namespace[name]


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


def test_number_selector_omits_absent_optional_unit():
    """Probatio rejects an explicit None for unit_of_measurement."""
    function = _function("_number")
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))

    captured: list[dict[str, Any]] = []

    class NumberSelectorConfig(dict):
        def __init__(self, **values: Any) -> None:
            super().__init__(values)
            captured.append(values)

    namespace: dict[str, Any] = {
        "Any": Any,
        "selector": SimpleNamespace(
            NumberSelectorConfig=NumberSelectorConfig,
            NumberSelector=lambda config: config,
            NumberSelectorMode=SimpleNamespace(BOX="box"),
        ),
    }
    exec(compile(module, str(CONFIG_FLOW), "exec"), namespace)
    number = namespace["_number"]

    unitless = number(0.5, 1.0, 0.01)
    with_unit = number(1, 32, 0.1, "A")

    assert unitless == {"min": 0.5, "max": 1.0, "step": 0.01, "mode": "box"}
    assert "unit_of_measurement" not in unitless
    assert with_unit["unit_of_measurement"] == "A"
    assert all(value is not None for config in captured for value in config.values())


def test_selector_config_calls_do_not_pass_literal_none():
    """Optional selector keys must be omitted instead of supplied as None."""
    tree = ast.parse(CONFIG_FLOW.read_text(encoding="utf-8"))
    selector_configs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.endswith("SelectorConfig")
    ]
    assert selector_configs
    for call in selector_configs:
        assert all(
            not (isinstance(keyword.value, ast.Constant) and keyword.value.value is None)
            for keyword in call.keywords
        )


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


def test_custom_normalisers_are_not_exposed_as_form_schema_validators():
    """Every custom text normaliser must run after Home Assistant form parsing."""
    schemas = {
        "_charger_schema": ("_connected_states", 1),
        "_schedule_schema": ("_normalise_month_list", 1),
    }

    for function_name, (normaliser, expected_text_selectors) in schemas.items():
        function = _function(function_name)
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
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Name) and node.id == normaliser
        ]

        assert len(text_selectors) == expected_text_selectors
        assert direct_normalisers == []


def test_config_and_options_steps_normalise_text_after_submit():
    """Both flow types normalise free text without breaking form serialisation."""
    tree = ast.parse(CONFIG_FLOW.read_text(encoding="utf-8"))
    expectations = {
        "async_step_charger": "_connected_states",
        "async_step_schedule": "_normalise_month_list",
    }

    for step_name, normaliser in expectations.items():
        steps = [
            node
            for parent in tree.body
            if isinstance(parent, ast.ClassDef)
            for node in parent.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == step_name
        ]
        assert len(steps) == 2
        for step in steps:
            assert any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == normaliser
                for call in ast.walk(step)
            )


def test_peak_months_normaliser_accepts_defaults_and_rejects_bad_values():
    """Schedule text remains validated after moving it out of the form schema."""
    function = _function("_normalise_month_list")
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))

    class Invalid(ValueError):
        pass

    namespace: dict[str, Any] = {
        "Any": Any,
        "cv": SimpleNamespace(string=lambda value: str(value)),
        "vol": SimpleNamespace(Invalid=Invalid),
    }
    exec(compile(module, str(CONFIG_FLOW), "exec"), namespace)
    validate = namespace["_normalise_month_list"]

    assert validate("12, 1, 2, 3, 6, 7, 8, 11, 12") == "1,2,3,6,7,8,11,12"
    for invalid in ("", "0,1", "1,13", "January"):
        try:
            validate(invalid)
        except Invalid:
            pass
        else:
            raise AssertionError(f"Invalid peak months accepted: {invalid!r}")


def test_limits_phase_values_convert_between_form_and_storage_types():
    """Selectors render strings while persisted configuration uses integers."""
    form_values = _compiled_function(
        "_limits_form_values",
        {
            "Any": Any,
            "CONF_PHASES": "phases",
            "PHASE_OPTION_SINGLE": "single_phase",
            "PHASE_OPTION_THREE": "three_phase",
        },
    )
    storage_values = _compiled_function(
        "_limits_storage_values",
        {
            "Any": Any,
            "CONF_PHASES": "phases",
            "PHASE_OPTION_SINGLE": "single_phase",
            "PHASE_OPTION_THREE": "three_phase",
            "vol": SimpleNamespace(Invalid=ValueError),
        },
    )

    assert form_values({"phases": 1, "other": 2}) == {
        "phases": "single_phase",
        "other": 2,
    }
    assert form_values({"phases": 3}) == {"phases": "three_phase"}
    assert form_values({"phases": "single_phase"}) == {"phases": "single_phase"}
    assert storage_values({"phases": "single_phase", "other": 2}) == {
        "phases": 1,
        "other": 2,
    }
    assert storage_values({"phases": "three_phase"}) == {"phases": 3}
    assert storage_values({"phases": "1"}) == {"phases": 1}


def test_schedule_progression_renders_limits_with_string_phase_default():
    """The initial flow's Schedule-to-Limits transition prepares selector types."""
    limits_schema = _function("_limits_schema")
    assert any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_limits_form_values"
        for call in ast.walk(limits_schema)
    )

    tree = ast.parse(CONFIG_FLOW.read_text(encoding="utf-8"))
    config_flow = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "JGEnergyConfigFlow"
    )
    schedule_step = next(
        node
        for node in config_flow.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_step_schedule"
    )
    assert any(
        isinstance(node, ast.Attribute) and node.attr == "async_step_limits"
        for node in ast.walk(schedule_step)
    )


def test_initial_and_options_limits_steps_store_integer_phases():
    """Both Limits handlers convert submitted selector strings before storage."""
    tree = ast.parse(CONFIG_FLOW.read_text(encoding="utf-8"))
    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name in {"JGEnergyConfigFlow", "JGEnergyOptionsFlow"}
    }

    assert set(classes) == {"JGEnergyConfigFlow", "JGEnergyOptionsFlow"}
    for class_node in classes.values():
        limits_step = next(
            node
            for node in class_node.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_step_limits"
        )
        assert any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_limits_storage_values"
            for call in ast.walk(limits_step)
        )

    options_step = next(
        node
        for node in classes["JGEnergyOptionsFlow"].body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_step_limits"
    )
    assert any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_limits_form_values"
        for call in ast.walk(options_step)
    )
    suggested_calls = [
        call
        for call in ast.walk(options_step)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "add_suggested_values_to_schema"
    ]
    assert len(suggested_calls) == 2
    for call in suggested_calls:
        assert len(call.args) == 2
        assert isinstance(call.args[1], ast.Name)
        assert call.args[1].id == "current"
