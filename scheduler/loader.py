import json
from pathlib import Path

from scheduler.models import Scenario

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "scenarios"


def list_scenarios() -> list[Path]:
    return sorted(DATA_DIR.glob("*.json"))


def load_scenario(path: Path | str) -> Scenario:
    scenario_path = Path(path)
    with scenario_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return Scenario.from_dict(data)
