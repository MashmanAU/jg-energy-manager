"""Load the pure planner without importing Home Assistant."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).parents[1] / "custom_components/jg_energy_manager/planner.py"
spec = importlib.util.spec_from_file_location("jg_energy_planner", MODULE)
planner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = planner
assert spec.loader is not None
spec.loader.exec_module(planner)
