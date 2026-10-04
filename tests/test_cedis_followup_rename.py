"""Synthetic checks for the CEDIS codebook sync (888 renamed, 889/891 added, 890 retired)."""
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("seaborn")

_PIPE = Path(tempfile.mkdtemp(prefix="medevac_test_pipe_"))
(_PIPE / "data" / "final" / "pediatric").mkdir(parents=True)
os.environ["MEDEVAC_PIPELINE_DIR"] = str(_PIPE)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis" / "python"))

import medevac_data_prep as prep  # noqa: E402
import medevac_summaries as summ  # noqa: E402


@pytest.mark.parametrize("cmap", [summ._CEDIS_CATEGORY_MAP, prep._CEDIS_CATEGORY_MAP])
def test_code_maps_cover_889_891_not_890(cmap):
    for code in (851, 888, 889, 891):
        assert cmap[code] == "General and Minor"
    assert 890 not in cmap
    assert 892 not in cmap


@pytest.mark.parametrize("text", ["Follow-up/Return Visit", "follow-up/return visit", "Follow-up visit"])
def test_follow_up_names_old_and_new_are_recognised_as_888(text):
    from cedis_policy import FOLLOW_UP, protected_code

    assert text.lower() in summ._FOLLOWUP_CC_TEXTS
    assert protected_code(None, text) == FOLLOW_UP


def _cc_frame():
    rows = [
        ("S1", 888, "Follow-up/Return Visit", 301, "Dysuria"),
        ("S2", 888, "Follow-up visit", 401, "Seizure"),
        ("S3", 889, "Well visit", 301, "Dysuria"),
        ("S4", 891, "Planned telehealth", 301, "Dysuria"),
        ("S5", 301, "Dysuria", 888, "Follow-up/Return Visit"),
    ]
    return pd.DataFrame(
        {
            "journey_id": [r[0] for r in rows],
            "village_cedis_code_1": [r[1] for r in rows],
            "village_cedis_complaint_1": [r[2] for r in rows],
            "village_cedis_code_2": [r[3] for r in rows],
            "village_cedis_complaint_2": [r[4] for r in rows],
        }
    )


def _cohort():
    return pd.DataFrame(
        {
            "journey_id": ["S1", "S2", "S3", "S4", "S5"],
            "age_at_medevac": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )


def test_definitive_cc_prefers_real_complaint_over_renamed_follow_up(monkeypatch, tmp_path):
    f = tmp_path / "cc.csv"
    _cc_frame().to_csv(f, index=False)
    monkeypatch.setattr(summ, "CHIEF_COMPLAINTS_WIDE", f)
    out = summ._definitive_cc_per_journey(_cohort()).set_index("journey_id")
    assert out.loc["S1", "cc_definitive"] == "Dysuria"
    assert out.loc["S2", "cc_definitive"] == "Seizure"
    assert out.loc["S3", "cc_definitive"] == "Well visit"
    assert out.loc["S3", "cc_definitive_category"] == "General and Minor"
    assert out.loc["S4", "cc_definitive"] == "Planned telehealth"
    assert out.loc["S5", "cc_definitive"] == "Dysuria"


def test_followup_validation_matches_new_name_by_text(monkeypatch, tmp_path):
    cc = _cc_frame().iloc[:4][["journey_id", "village_cedis_code_1", "village_cedis_complaint_1"]].copy()
    cc["village_cedis_code_1"] = pd.NA  # force text-only matching
    f = tmp_path / "cc.csv"
    cc.to_csv(f, index=False)
    monkeypatch.setattr(summ, "CHIEF_COMPLAINTS_WIDE", f)
    monkeypatch.setattr(summ, "MISSED_OPPORTUNITIES_CSV", tmp_path / "missing.csv")
    out = summ.build_table3_followup_prior_visit_check(_cohort()).set_index("group")
    assert out.loc["Follow-up/Return Visit (CEDIS 888)", "journeys_n"] == 2  # S1 + S2 (old name)
    assert out.loc["All cohort journeys", "journeys_n"] == 5  # S5 absent from CC file but still in cohort
