"""
Synthetic tests (no PHI) for the standing rule: CEDIS 888 / 889 / 891 never
exclude a journey, count, table row or figure element. They may only lose the
"which complaint is definitive" choice to another real complaint on the same
journey, and fall back to themselves when nothing else exists.
"""

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis" / "python"))

# medevac_data_prep resolves its data directory at import time; point it at an
# empty synthetic location so the tests never touch real data.
_fake_pipeline = Path(tempfile.mkdtemp(prefix="cedis_test_pipeline_"))
(_fake_pipeline / "data" / "final" / "pediatric").mkdir(parents=True)
os.environ.setdefault("MEDEVAC_PIPELINE_DIR", str(_fake_pipeline))

import cedis_policy as pol  # noqa: E402
import medevac_data_prep as prep  # noqa: E402
import medevac_summaries as summ  # noqa: E402

FU, WELL, TELE = "Follow-up visit", "Well visit", "Planned telehealth"


def test_policy_ranks():
    assert pol.definitive_rank(888, FU) == pol.RANK_FOLLOW_UP
    assert pol.definitive_rank("888.0", None) == pol.RANK_FOLLOW_UP
    assert pol.definitive_rank(None, "Follow-up/Return Visit") == pol.RANK_FOLLOW_UP
    assert pol.definitive_rank(889, WELL) == pol.RANK_NORMAL
    assert pol.definitive_rank(891, TELE) == pol.RANK_NORMAL
    assert pol.definitive_rank(None, "planned telehealth") == pol.RANK_NORMAL
    assert pol.definitive_rank(851, "Fever") == pol.RANK_NORMAL
    assert pol.definitive_rank(999, "Unknown") is None
    assert pol.definitive_rank(None, "unknown") is None
    assert pol.definitive_rank(851, "") is None
    assert pol.definitive_rank(pd.NA, pd.NA) is None


def test_pick_definitive_tiers():
    assert pol.pick_definitive([(888, FU)]) == 0
    assert pol.pick_definitive([(888, FU), (651, "Cough")]) == 1
    assert pol.pick_definitive([(889, WELL), (651, "Cough")]) == 0
    assert pol.pick_definitive([(891, TELE)]) == 0
    assert pol.pick_definitive([(999, "Unknown"), (888, FU)]) == 1
    assert pol.pick_definitive([(999, "Unknown")]) is None
    assert pol.pick_definitive([]) is None


def _long(rows):
    return pd.DataFrame(
        rows,
        columns=["journey_id", "facility_phase", "cc_sequence", "EncounterStartDTS", "cedis_code", "cedis_complaint"],
    )


def test_data_prep_keeps_journeys_whose_only_complaint_is_protected():
    ts = "2024-01-01 10:00"
    cc = _long([
        ["A", "village", 1, ts, 888, FU],
        ["B", "village", 1, ts, 888, FU],
        ["B", "mhc_ed", 1, ts, 651, "Cough"],
        ["C", "village", 1, ts, 889, WELL],
        ["C", "mhc_ed", 1, ts, 651, "Cough"],
        ["D", "village", 1, ts, 891, TELE],
        ["E", "village", 1, ts, 999, "Unknown"],
        ["E", "mhc_ed", 1, ts, 888.0, FU],
        ["F", "village", 1, ts, 888, None],
        ["G", "village", 1, ts, 999, "Unknown"],
    ])
    out = prep._build_definitive_cc(cc).set_index("journey_id")

    assert out.loc["A", "primary_cedis_code"] == 888
    assert out.loc["A", "primary_cedis_complaint"] == FU
    assert out.loc["A", "primary_cedis_custom_group"] == FU
    assert out.loc["B", "primary_cedis_complaint"] == "Cough"
    assert out.loc["C", "primary_cedis_code"] == 889
    assert out.loc["D", "primary_cedis_code"] == 891
    assert out.loc["D", "primary_cedis_complaint"] == TELE
    assert out.loc["E", "primary_cedis_code"] == 888
    assert out.loc["F", "primary_cedis_complaint"] == FU
    assert out.loc["A", "primary_cedis_category"] == "General and Minor"
    assert out.loc["D", "primary_cedis_category"] == "General and Minor"
    # Unknown-only journeys have no usable complaint (not an 888/889/891 case).
    assert "G" not in out.index


def test_data_prep_village_888_is_replaced_by_later_real_complaint():
    cc = _long([
        ["A", "village", 1, "2024-01-01", 888, FU],
        ["A", "anmc_ed", 1, "2024-01-02", 401, "Seizure"],
    ])
    out = prep._build_definitive_cc(cc).set_index("journey_id")
    assert out.loc["A", "primary_cedis_complaint"] == "Seizure"


def _wide(tmp_path, monkeypatch, rows):
    cols = ["journey_id"]
    for i in (1, 2):
        cols += [f"village_cedis_complaint_{i}", f"village_cedis_code_{i}"]
    cols += ["mhc_ed_cedis_complaint_1", "mhc_ed_cedis_code_1"]
    p = tmp_path / "cc_wide.csv"
    pd.DataFrame(rows, columns=cols).to_csv(p, index=False)
    monkeypatch.setattr(summ, "CHIEF_COMPLAINTS_WIDE", p)


def test_summaries_definitive_cc_never_drops_journeys(tmp_path, monkeypatch):
    n = None
    _wide(tmp_path, monkeypatch, [
        ["A", FU, 888, n, n, n, n],
        ["B", FU, 888, "Cough", 651, n, n],
        ["C", WELL, 889, "Cough", 651, n, n],
        ["D", TELE, 891, n, n, n, n],
        ["E", "Unknown", 999, n, n, FU, 888],
        ["F", "Unknown", 999, n, n, n, n],
    ])
    df = pd.DataFrame({
        "journey_id": list("ABCDEFZ"),
        "age_at_medevac": [2.0] * 7,
    })
    out = summ._definitive_cc_per_journey(df).set_index("journey_id")

    assert len(out) == 7
    assert out.loc["A", "cc_definitive"] == FU
    assert out.loc["A", "cc_definitive_code"] == "888"
    assert out.loc["A", "cc_definitive_custom_grouping"] == FU
    assert out.loc["B", "cc_definitive"] == "Cough"
    assert out.loc["C", "cc_definitive"] == WELL
    assert out.loc["D", "cc_definitive"] == TELE
    assert out.loc["D", "cc_definitive_category"] == "General and Minor"
    assert out.loc["E", "cc_definitive"] == FU
    for jid in "ABCDE":
        assert out.loc[jid, "cc_definitive_custom_grouping"] != "Undefined"
    assert out.loc["F", "cc_definitive_custom_grouping"] == "Undefined"


def test_table_4_6_keeps_888_only_journey(tmp_path, monkeypatch):
    n = None
    _wide(tmp_path, monkeypatch, [
        ["A", FU, 888, n, n, n, n],
        ["B", FU, 888, "Cough", 651, n, n],
    ])
    df = pd.DataFrame({"journey_id": ["A", "B"], "age_at_medevac": [2.0, 3.0]})
    out = summ.build_table4_6_expanded_followup_cc_review(df)
    by_j = out.drop_duplicates("journey_id").set_index("journey_id")
    assert set(by_j.index) == {"A", "B"}
    assert str(by_j.loc["A", "expanded_cc_code"]) == "888"
    assert by_j.loc["A", "expanded_cc_fu"] == "No"
    assert str(by_j.loc["B", "expanded_cc_code"]) == "651"
    assert by_j.loc["B", "expanded_cc_fu"] == "Yes"


@pytest.mark.parametrize("code,label", [(888, FU), (889, WELL), (891, TELE)])
def test_single_protected_complaint_is_counted_in_top_table(code, label):
    cc = pd.DataFrame({
        "journey_id": ["1", "2"],
        "cedis_code": [str(code), "651"],
        "cedis_complaint": [label, "Cough"],
    })
    out = summ._top10_chief_complaints(cc, 2)
    assert label in set(out["Chief Complaint"])
