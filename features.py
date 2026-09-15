"""Unscripted - candidate signals for telling a read answer from a spontaneous one.

Exploratory by design. signals.py holds the one measurement the report currently
acts on; this module measures everything that plausibly differs between reading
and thinking out loud, so scripts/evaluate.py can check each one against answers
whose delivery is known. A feature earns a place in the decision only by
separating those answers on sessions it was not tuned on.

Pure functions: a list of words in (as Speechmatics timed them), numbers out.
Every feature is None when it cannot be computed, never 0: zero hesitations and
"hesitations could not be counted" are different facts.

What each family is after:
- TIMING. Thinking produces bursts of words and stops while the next idea forms;
  reading evens the gaps and keeps runs of words long.
- DISFLUENCY. Restarts, repeated words and "uh" come from planning speech on the
  fly. A written text has none to read.
- LEXICON. Text written in advance, and especially by a chatbot, uses longer and
  more varied words and fewer conversational fillers than speech made up live.
- REGISTER. Speech built on the fly restarts itself ("the agent try to understand
  the agent, try to understand"), runs sentences together and contracts words.
  A text read aloud comes out in finished sentences, with the nominalisations and
  connectors of written prose.
- CONFIDENCE. The recogniser's own confidence: read speech tends to be clearer.
"""
from __future__ import annotations

import re
import statistics

# A silence at least this long between two words is a pause. Short enough to
# catch the breath between phrases, long enough to ignore the gap between syllables
# that the recogniser sometimes leaves.
PAUSE = 0.25
LONG_PAUSE = 1.0
# Beyond this, a gap is a stop, not part of the pace: kept out of the variation
# measures so one long think does not decide on its own.
GAP_CEILING = 3.0
MATTR_WINDOW = 20

FILLERS = {"like", "actually", "basically", "just", "really", "so", "well", "yeah",
           "okay", "ok", "right", "anyway", "stuff", "things", "kinda", "sorta"}
FILLER_PAIRS = {("you", "know"), ("i", "mean"), ("kind", "of"), ("sort", "of"), ("i", "guess")}

# Connectors that belong to written, and especially generated, prose. Rare in
# speech made up live, where "and", "so" and "but" do that work.
WRITTEN_CONNECTORS = {"additionally", "furthermore", "moreover", "ultimately", "consequently",
                      "overall", "therefore", "thereby", "whereas", "while", "ensuring",
                      "leveraging", "resulting", "specifically", "notably", "however"}
NOMINAL_SUFFIXES = ("tion", "sion", "ment", "ness", "ity", "ance", "ence", "ism")
# A repeated pair of words this close is a restart, not style.
RESTART_WINDOW = 6

_LETTERS = re.compile(r"[^a-z']")


def _token(word: dict) -> str:
    return _LETTERS.sub("", word["text"].lower())


def _cv(values: list[float]) -> float | None:
    if len(values) < 5:
        return None
    mean = statistics.fmean(values)
    return statistics.pstdev(values) / mean if mean > 0 else None


def _per100(count: int, n: int) -> float | None:
    return 100 * count / n if n else None


def timing(words: list[dict]) -> dict:
    n = len(words)
    out = dict.fromkeys(["wpm", "articulation_wpm", "onset_cv", "gap_cv", "pause_rate",
                         "long_pause_rate", "mean_run", "run_cv", "mean_pause"])
    if n < 2:
        return out
    gaps = [max(0.0, b["start"] - a["end"]) for a, b in zip(words, words[1:])]
    spoken = words[-1]["end"] - words[0]["start"]
    if spoken > 0:
        out["wpm"] = 60 * n / spoken
        paused = sum(g for g in gaps if g >= PAUSE)
        if spoken - paused > 0:
            out["articulation_wpm"] = 60 * n / (spoken - paused)

    onsets = [b["start"] - a["start"] for a, b in zip(words, words[1:])]
    out["onset_cv"] = _cv([d for d in onsets if 0 < d <= GAP_CEILING])
    out["gap_cv"] = _cv([g for g in gaps if g <= GAP_CEILING])

    pauses = [g for g in gaps if g >= PAUSE]
    out["pause_rate"] = _per100(len(pauses), n)
    out["long_pause_rate"] = _per100(sum(1 for g in gaps if g >= LONG_PAUSE), n)
    capped = [min(g, GAP_CEILING) for g in pauses]
    out["mean_pause"] = statistics.fmean(capped) if capped else 0.0

    runs, run = [], 1
    for g in gaps:
        if g >= PAUSE:
            runs.append(run)
            run = 1
        else:
            run += 1
    runs.append(run)
    out["mean_run"] = statistics.fmean(runs)
    out["run_cv"] = _cv([float(r) for r in runs])
    return out


def disfluency(words: list[dict]) -> dict:
    n = len(words)
    tokens = [_token(w) for w in words]
    repeats = sum(1 for a, b in zip(tokens, tokens[1:]) if a and a == b)
    return {
        "hesitation_rate": _per100(sum(1 for w in words if w.get("disfluency")), n),
        "repetition_rate": _per100(repeats, n),
    }


def lexicon(words: list[dict]) -> dict:
    """None throughout when the words carry no text (the anonymised fixtures)."""
    tokens = [_token(w) for w in words if not w.get("disfluency")]
    tokens = [t for t in tokens if t]
    out = dict.fromkeys(["mean_word_length", "long_word_share", "mattr", "filler_rate"])
    if len(tokens) < 10 or len(set(tokens)) <= 1:
        return out
    out["mean_word_length"] = statistics.fmean(len(t.replace("'", "")) for t in tokens)
    out["long_word_share"] = sum(1 for t in tokens if len(t) >= 7) / len(tokens)
    if len(tokens) >= MATTR_WINDOW:
        windows = [tokens[i:i + MATTR_WINDOW] for i in range(len(tokens) - MATTR_WINDOW + 1)]
        out["mattr"] = statistics.fmean(len(set(w)) / MATTR_WINDOW for w in windows)
    fillers = sum(1 for t in tokens if t in FILLERS)
    fillers += sum(1 for pair in zip(tokens, tokens[1:]) if pair in FILLER_PAIRS)
    out["filler_rate"] = _per100(fillers, len(tokens))
    return out


def register(words: list[dict]) -> dict:
    """None throughout when the words carry no text (the anonymised fixtures)."""
    out = dict.fromkeys(["restart_rate", "words_per_sentence", "comma_rate", "contraction_rate",
                         "nominal_share", "connector_rate"])
    spoken = [w for w in words if not w.get("disfluency")]
    tokens = [_token(w) for w in spoken]
    if len([t for t in tokens if t]) < 10 or len(set(tokens)) <= 1:
        return out
    n = len(tokens)

    # A restart: the same two words again within a few words, the second time
    # starting after the first pair ended ("try to understand, uh, try to understand").
    restarts, i = 0, 0
    while i < n - 1:
        pair = (tokens[i], tokens[i + 1])
        hit = next((j for j in range(i + 2, min(n - 1, i + 2 + RESTART_WINDOW))
                    if (tokens[j], tokens[j + 1]) == pair and all(pair)), None)
        if hit is not None:
            restarts += 1
            i = hit + 2
        else:
            i += 1
    out["restart_rate"] = _per100(restarts, n)

    sentences = sum(1 for w in spoken if w.get("boundary"))
    out["words_per_sentence"] = n / max(1, sentences)
    out["comma_rate"] = _per100(sum(1 for w in spoken if w["text"].endswith(",")), n)
    out["contraction_rate"] = _per100(sum(1 for t in tokens if "'" in t.strip("'")), n)
    out["nominal_share"] = sum(1 for t in tokens if len(t) > 5 and t.endswith(NOMINAL_SUFFIXES)) / n
    out["connector_rate"] = _per100(sum(1 for t in tokens if t in WRITTEN_CONNECTORS), n)
    return out


def confidence(words: list[dict]) -> dict:
    values = [w["confidence"] for w in words if isinstance(w.get("confidence"), (int, float))]
    return {"mean_confidence": statistics.fmean(values) if values else None}


def extract(words: list[dict], question_end: float | None) -> dict:
    out = {"words": len(words),
           "latency": (words[0]["start"] - question_end) if words and question_end is not None else None}
    for family in (timing, disfluency, lexicon, register, confidence):
        out.update(family(words))
    # Hesitations, repeated words and restarts are each too rare in one answer to
    # count on alone; together they are how often speech had to repair itself.
    parts = [out["hesitation_rate"], out["repetition_rate"], out["restart_rate"]]
    out["disfluency_rate"] = sum(parts) if all(p is not None for p in parts) else None
    return out


FEATURES = ["latency", "wpm", "articulation_wpm", "onset_cv", "gap_cv", "pause_rate",
            "long_pause_rate", "mean_run", "run_cv", "mean_pause", "hesitation_rate",
            "repetition_rate", "mean_word_length", "long_word_share", "mattr", "filler_rate",
            "restart_rate", "words_per_sentence", "comma_rate", "contraction_rate", "nominal_share",
            "connector_rate", "disfluency_rate", "mean_confidence"]


def relative(answer: dict, baseline: dict) -> dict:
    """Each feature as answer / warm-up, when both exist and the warm-up's is not 0.

    The speaker is compared with themselves: some people pause a lot whatever
    they do, and it is the change from their own warm-up that could mean reading.
    """
    out = {}
    for name in FEATURES:
        a, b = answer.get(name), baseline.get(name)
        out[f"{name}/base"] = a / b if a is not None and b not in (None, 0) else None
    return out
