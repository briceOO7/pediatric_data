"""
Synthetic tests (no PHI): a missing / 999 / Unknown / Undefined chief complaint
never drops a journey from a complaint table. Such journeys get an explicit
"Unknown/Undefined" row, and complaints below the reporting threshold are pooled
into "Other", so table rows always sum to the journey total.
"""

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis" / "python"))

_fake_pipeline = Path(tempfile.mkdtemp(prefix="cedis_test_pipeline_"))
(_fake_pipeline / "data" / "final" / "pediatric").mkdir(parents=True)
os.environ.setdefault("MEDEVAC_PIPELINE_DIR", str(_fake_pipeline))

import cedis_policy as pol  # noqa: E402
import medevac_summaries as summ  # noqa: E402


def test_display_groups_keep_every_journey():
    labels = pd.Series(
        ["Fever"] * 12 + ["Cough"] * 10 + ["Rash"] * 3 + ["Ear pain"] * 2
        + [None, "", "Unknown", "Undefined", pd.NA]
    )
    display, levels, other = pol.complaint_display_groups(labels, min_n=10)
    assert len(display) == len(labels) and display.notna().all()
    assert levels == ["Fever", "Cough", "Other", "Unknown/Undefined"]
    assert display.value_counts().to_dict() == {
        "Fever": 12, "Cough": 10, "Other": 5, "Unknown/Undefined": 5,
    }
    assert other == {"Rash": 3, "Ear pain": 2}


def test_display_groups_omit_empty_other_and_unknown_rows():
    display, levels, other = pol.complaint_display_groups(pd.Series(["Fever"] * 11), min_n=10)
    assert levels == ["Fever"] and other == {}
    assert display.tolist() == ["Fever"] * 11


def _ids_df(n):
    return pd.DataFrame({"journey_id": [str(i) for i in range(n)], "age_at_medevac": [2.0] * n})


def test_top_table_rows_sum_to_journey_total():
    rows = [(str(651), "Cough")] * 4 + [(str(851), "Fever")] * 3 + [(str(402), "Seizure")]
    rows += [("999", "Unknown"), (None, None), ("", "")]
    cc = pd.DataFrame(rows, columns=["cedis_code", "cedis_complaint"])
    cc["journey_id"] = [str(i) for i in range(len(cc))]
    out = summ._top10_chief_complaints(cc, len(cc), min_overall=3)
    names = out["Chief Complaint"].tolist()
    assert names[:2] == ["Cough", "Fever"]
    assert names[-2].startswith("Other (1 complaints")
    assert names[-1] == "Unknown/Undefined"
    ns = [int(s.split(" ")[0]) for s in out["n(%)"]]
    assert sum(ns) == len(cc)


def test_cedis_chief_complaints_table_by_age_keeps_all_journeys(tmp_path, monkeypatch):
    cols = ["journey_id", "village_cedis_complaint_1", "village_cedis_code_1"]
    rows = (
        [[f"c{i}", "Cough", 651] for i in range(12)]
        + [[f"r{i}", "Rash", 1] for i in range(3)]
        + [["u1", "Unknown", 999], ["u2", None, None]]
    )
    wide = tmp_path / "cc_wide.csv"
    pd.DataFrame(rows, columns=cols).to_csv(wide, index=False)
    monkeypatch.setattr(summ, "CHIEF_COMPLAINTS_WIDE", wide)
    monkeypatch.setattr(summ, "ROOT", tmp_path)
    monkeypatch.setattr(summ, "OUT_TABLES", tmp_path / "outputs" / "tables")
    (tmp_path / "outputs" / "tables").mkdir(parents=True)

    df = pd.DataFrame({"journey_id": [r[0] for r in rows], "age_at_medevac": [2.0] * len(rows)})
    out = summ.build_table3_cedis_chief_complaints(df, min_overall=10)

    assert out["Chief Complaint (CEDIS)"].tolist() == ["Cough", "Other", "Unknown/Undefined"]
    overall_n = [int(s.split(" ")[0]) for s in out["Overall"]]
    assert overall_n == [12, 3, 2] and sum(overall_n) == len(rows)
    other = pd.read_csv(tmp_path / "outputs" / "tables" / "table3_cedis_chief_complaints_other_complaints.csv")
    assert other.to_dict("records") == [{"complaint": "Rash", "n_journeys": 3}]
