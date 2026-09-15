"""Probe - does this answer sound prepared, and what should the interviewer do next?

The voice agent calls the `assess_answer` tool when a candidate finishes an
answer. This module turns the AssemblyAI words of that answer into the result the
agent reads: a decision computed by code, the reasons behind it, and a single
instruction for the next thing to say.

Two rules carried over from Unscripted:

- THE MODEL OBSERVES, THE CODE DECIDES. The language model conducting the
  interview never judges whether an answer was read. It receives the verdict and
  its reasons, and chooses the wording of the follow-up.
- NOTHING MEASURED IS NOT A PASS. An answer too short to measure, or a warm-up
  too short to compare against, says so and asks for nothing.
"""
from __future__ import annotations

import detector
import features

MIN_WORDS = 25
MIN_BASELINE_WORDS = 15

# AssemblyAI's streaming transcript keeps filler words verbatim but does not tag
# them, so they are recognised by their text.
FILLERS = {"um", "uh", "uhm", "umm", "er", "erm", "ah", "hmm", "mm", "mhm"}


def from_assemblyai(words: list[dict]) -> list[dict]:
    """AssemblyAI streaming words (milliseconds) into the shape features.py reads (seconds)."""
    out = []
    for w in words:
        text = str(w.get("text", ""))
        bare = text.strip(" ,.?!;:").lower()
        out.append({
            "text": text,
            "start": w["start"] / 1000,
            "end": w["end"] / 1000,
            "confidence": w.get("confidence"),
            "disfluency": bare in FILLERS,
            "boundary": text.rstrip().endswith((".", "?", "!")),
        })
    return out


def words_between(words: list[dict], start_s: float, end_s: float | None) -> list[dict]:
    """The words that started inside [start_s, end_s)."""
    return [w for w in words if w["start"] >= start_s and (end_s is None or w["start"] < end_s)]


def _guidance(kind: str, reasons: list[str]) -> str:
    if kind == "prepared":
        because = "; ".join(reasons) if reasons else "several signals lean that way"
        return ("This answer sounds prepared rather than thought through on the spot "
                f"({because}). Ask exactly one short follow-up that makes the candidate go beyond "
                "a script: a concrete detail, a moment something went wrong, a trade-off they chose, "
                "or why they made one specific decision they mentioned. Refer to their own words. "
                "Never say or hint that the answer sounded prepared or read.")
    if kind == "spontaneous":
        return "This answer sounds spontaneous. Do not probe it; move on to the next question."
    if kind == "baseline":
        return "This was the warm-up. Thank the candidate briefly and ask the next question."
    return "This answer was too short to assess. Do not probe it; move on to the next question."


def assess(answer: list[dict], baseline: list[dict] | None, model: dict | None = None) -> dict:
    """The verdict for one answer, in words the agent and the report can both use.

    `answer` and `baseline` are words already converted by `from_assemblyai`.
    Pass `baseline=None` when assessing the warm-up itself.
    """
    model = model or detector.load()
    result = {"words": len(answer), "measured": False, "sounds_prepared": None,
              "score": None, "threshold": model["threshold"], "reasons": [], "signals": {}}

    if baseline is None:
        result["verdict"] = "baseline"
        result["instruction"] = _guidance("baseline", [])
        return result
    if len(answer) < MIN_WORDS or len(baseline) < MIN_BASELINE_WORDS:
        result["verdict"] = "not_measured"
        result["instruction"] = _guidance("not_measured", [])
        return result

    own = features.extract(answer, None)
    base = features.extract(baseline, None)
    row = {**own, **features.relative(own, base)}
    scored = detector.score(row, model)
    result["signals"] = {s["name"]: row.get(s["name"]) for s in model["signals"]}
    if scored["score"] is None:
        result["verdict"] = "not_measured"
        result["instruction"] = _guidance("not_measured", [])
        return result

    reasons = [detector.EXPLANATIONS[n] for n in scored["pointing_to_reading"] if n in detector.EXPLANATIONS]
    kind = "prepared" if scored["suggests_reading"] else "spontaneous"
    result.update(measured=True, sounds_prepared=scored["suggests_reading"], score=scored["score"],
                  reasons=reasons if kind == "prepared" else [], verdict=kind,
                  instruction=_guidance(kind, reasons))
    return result
