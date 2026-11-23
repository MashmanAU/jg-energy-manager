#!/usr/bin/env python3
"""Verify that the built HACS archive cannot contain the reproduced validator bug."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "dist" / "jg_energy_manager.zip"
EXPECTED_FILES = {
    "config_flow.py",
    "const.py",
    "actuator.py",
    "session.py",
    "runtime.py",
    "input_snapshot.py",
    "coordinator.py",
    "sensor.py",
    "manifest.json",
    "strings.json",
    "translations/en.json",
}
SCHEMA_BUILDERS = {
    "_energy_schema",
    "_charger_schema",
    "_schedule_schema",
    "_limits_schema",
    "_control_schema",
    "_secondary_schema",
}


def main() -> None:
    if not ARCHIVE.is_file():
        raise SystemExit(f"Missing release archive: {ARCHIVE}")

    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(ARCHIVE) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise SystemExit("HACS archive contains duplicate members")
            missing = EXPECTED_FILES.difference(names)
            if missing:
                raise SystemExit(f"HACS archive missing: {', '.join(sorted(missing))}")
            archive.testzip()
            archive.extractall(target)

        source = (target / "config_flow.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function_names = {
            node.name for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        if "_peak_months" in source or "_peak_months" in function_names:
            raise SystemExit("HACS archive still defines the legacy _peak_months function")
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        missing_builders = SCHEMA_BUILDERS.difference(functions)
        if missing_builders:
            raise SystemExit(
                f"Missing schema builders: {', '.join(sorted(missing_builders))}"
            )

        for name in SCHEMA_BUILDERS:
            function = functions[name]
            for node in ast.walk(function):
                if isinstance(node, ast.Name) and node.id in {
                    "_normalise_month_list",
                    "_connected_states",
                    "_charging_states",
                }:
                    raise SystemExit(
                        f"{name} embeds custom callable validator {node.id}"
                    )

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if not (
                isinstance(function, ast.Attribute)
                and function.attr.endswith("SelectorConfig")
            ):
                continue
            for keyword in node.keywords:
                if isinstance(keyword.value, ast.Constant) and keyword.value.value is None:
                    raise SystemExit(
                        f"Selector config {function.attr} explicitly passes None to "
                        f"{keyword.arg}"
                    )

        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        strings = json.loads((target / "strings.json").read_text(encoding="utf-8"))
        translation = json.loads(
            (target / "translations" / "en.json").read_text(encoding="utf-8")
        )
        if strings != translation:
            raise SystemExit("HACS archive strings and English translation differ")

        sensor_tree = ast.parse((target / "sensor.py").read_text(encoding="utf-8"))
        remaining = next(
            call
            for call in ast.walk(sensor_tree)
            if isinstance(call, ast.Call)
            and any(
                keyword.arg == "key"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == "energy_remaining"
                for keyword in call.keywords
            )
        )
        remaining_keywords = {keyword.arg: keyword.value for keyword in remaining.keywords}
        state_class = remaining_keywords.get("state_class")
        if not (
            isinstance(state_class, ast.Attribute)
            and state_class.attr == "MEASUREMENT"
            and "device_class" not in remaining_keywords
        ):
            raise SystemExit(
                "Remaining allowance must retain measurement statistics without "
                "an incompatible energy device class"
            )

        limits = strings["config"]["step"]["limits"]
        required_labels = {
            "min_current_a",
            "max_current_a",
            "max_charger_power_w",
            "battery_max_charge_power_w",
            "grid_tolerance_w",
            "current_step_a",
            "ramp_up_step_a",
            "force_charge_current_a",
            "supply_voltage",
            "phases",
            "charging_efficiency",
            "solar_start_margin_w",
            "solar_run_margin_w",
            "idle_power_w",
        }
        missing_labels = required_labels.difference(limits["data"])
        if missing_labels:
            raise SystemExit(
                f"Limits translations missing: {', '.join(sorted(missing_labels))}"
            )

    print(
        f"Verified HACS archive {manifest['version']}: no legacy _peak_months "
        "schema validator or duplicate members"
    )


if __name__ == "__main__":
    main()
