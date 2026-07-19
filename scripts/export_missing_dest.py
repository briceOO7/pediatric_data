"""
Export journeys missing destination_datetime for hand review.
Run from the project root:

    python scripts/export_missing_dest.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "analysis" / "python"))

from medevac_summaries import (
    load_data,
    filter_journeys_village_to_mhc,
    export_missing_destination_datetime,
)

df = filter_journeys_village_to_mhc(load_data())
export_missing_destination_datetime(df)
