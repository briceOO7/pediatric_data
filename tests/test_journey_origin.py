import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis" / "python"))

from journey_origin import ENV_VAR, journey_origins, parse_journey_origins, split_by_journey_origin  # noqa: E402


def test_default_and_env_override(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert journey_origins() == ["village"]
    monkeypatch.setenv(ENV_VAR, "mhc, village")
    assert journey_origins() == ["mhc", "village"]
    with pytest.raises(ValueError):
        parse_journey_origins("anmc")


def test_split_uses_journey_origin():
    df = pd.DataFrame({
        "journey_id": ["JV-1", "JH-2", "JV-3", "X-4"],
        "journey_origin": ["village", "mhc", "VILLAGE", None],
    })
    kept, dropped = split_by_journey_origin(df, ["village"])
    assert kept["journey_id"].tolist() == ["JV-1", "JV-3"]
    assert dropped["journey_id"].tolist() == ["JH-2", "X-4"]
    kept, dropped = split_by_journey_origin(df, ["village", "mhc"])
    assert dropped["journey_id"].tolist() == ["X-4"]


def test_older_outputs_without_journey_origin_are_untouched():
    df = pd.DataFrame({"journey_id": ["1", "2"], "origin_type": ["village_mhc", "mhc_anmc"]})
    kept, dropped = split_by_journey_origin(df, ["village"])
    assert kept.equals(df)
    assert dropped.empty
