"""Unscripted - the frozen detector: does an answer sound read or made up on the spot?

It combines four signals, each measured on the answer and, where that makes
sense, against the same speaker's warm-up (see scripts/fit.py for why these
four). Each signal is put on a common scale using the spread seen in
calibration, turned so that higher always means "more like a text being read",
and averaged. Above the threshold, the answer is worth revisiting.

The parameters live in detector.json, written by scripts/fit.py. They are data,
not code, so a re-calibration changes one reviewed file and the report can say
exactly what the result rests on.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

DETECTOR_FILE = Path(__file__).with_name("detector.json")

# What each signal means for a recruiter, in the direction that points to reading.
EXPLANATIONS = {
    "long_word_share/base": "vocabulary closer to written text than in the warm-up",
    "disfluency_rate": "few hesitations, repeated words or restarts",
    "comma_rate/base": "fewer run-on clauses than in the warm-up",
    "mean_run/base": "longer stretches of words without a pause than in the warm-up",
}


def load(path: Path = DETECTOR_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def score(row: dict, model: dict) -> dict:
    """The score for one answer's features, and which signals pushed it up.

    None when fewer than three of the four signals could be measured: an
    average of one or two would be a different, untested detector.
    """
    parts = []
    for signal in model["signals"]:
        value = row.get(signal["name"])
        if value is None:
            continue
        z = (value - signal["mean"]) / signal["sd"]
        parts.append((signal["name"], z if signal["direction"] == "higher" else -z))
    if len(parts) < len(model["signals"]) - 1:
        return {"score": None, "suggests_reading": None, "pointing_to_reading": [], "measured": len(parts)}
    total = statistics.fmean(z for _, z in parts)
    return {
        "score": round(total, 3),
        "suggests_reading": total > model["threshold"],
        # Only signals clearly on the reading side are named: a recruiter should
        # see what the remark rests on, not a list of everything measured.
        "pointing_to_reading": [name for name, z in sorted(parts, key=lambda p: -p[1]) if z > 0.5],
        "measured": len(parts),
    }
