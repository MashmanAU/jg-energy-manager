"""Static metadata regressions that do not require Home Assistant imports."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_maximum_energy_remaining_has_no_measurement_state_class():
    source = ROOT / "custom_components" / "jg_energy_manager" / "sensor.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    sensors = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SENSORS" for target in node.targets)
    )
    energy_remaining = next(
        call
        for call in ast.walk(sensors.value)
        if isinstance(call, ast.Call)
        and any(
            keyword.arg == "key"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "energy_remaining"
            for keyword in call.keywords
        )
    )
    keyword_names = {keyword.arg for keyword in energy_remaining.keywords}
    assert "state_class" not in keyword_names


def test_runtime_migrates_legacy_override_values_to_operating_modes():
    source = ROOT / "custom_components" / "jg_energy_manager" / "runtime.py"
    text = source.read_text(encoding="utf-8")
    assert '"force_max": "force_charge"' in text
    assert '"force_off": "off"' in text
