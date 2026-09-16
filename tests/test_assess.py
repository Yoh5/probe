"""The verdict the voice agent reads after each answer."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import assess  # noqa: E402

MODEL = {
    "threshold": -0.2,
    "signals": [
        {"name": "long_word_share/base", "direction": "higher", "mean": 2.18, "sd": 1.13},
        {"name": "disfluency_rate", "direction": "lower", "mean": 2.75, "sd": 2.41},
        {"name": "comma_rate/base", "direction": "lower", "mean": 0.80, "sd": 0.71},
        {"name": "mean_run/base", "direction": "higher", "mean": 1.19, "sd": 0.32},
    ],
}

CHATTY = ("so yesterday I, uh, I got up pretty early, went to the gym, and then, you know, "
          "I went to work and I did my stuff, and then I, I came back home and I just cooked, "
          "watched a show, and went to bed")
CHATTY_2 = ("well I built a tool, uh, a small tool, for cleaning data, and the hard part was, "
            "you know, the files, the files were messy, so I, I wrote checks, and it kind of "
            "worked, and I learned a lot from it, really")
WRITTEN = ("I designed an intelligent data cleaning platform as the sole developer. The architecture "
           "combined a profiling engine detecting missing values and inferring column types, a "
           "recommendation engine suggesting cleaning strategies, and a generator producing validated "
           "Python scripts. Handling inconsistent delimiters taught me defensive programming.")


def aai_words(text, start_ms=0, pause_every=4, pause_ms=600):
    """Words shaped like AssemblyAI's streaming output: milliseconds, punctuation in the text."""
    out, t = [], start_ms
    for i, token in enumerate(text.split()):
        out.append({"text": token, "start": t, "end": t + 250, "confidence": 0.95, "word_is_final": True})
        t += 250 + (pause_ms if (i + 1) % pause_every == 0 else 50)
    return out


def converted(text, **kw):
    return assess.from_assemblyai(aai_words(text, **kw))


# -- the adapter -------------------------------------------------------------------------

def test_milliseconds_become_seconds_and_fillers_are_recognised():
    w = assess.from_assemblyai([{"text": "Um,", "start": 1200, "end": 1500, "confidence": 0.8},
                                {"text": "done.", "start": 1600, "end": 2000, "confidence": 0.9}])
    assert w[0]["start"] == 1.2 and w[0]["end"] == 1.5
    assert w[0]["disfluency"] is True and w[1]["disfluency"] is False
    assert w[0]["boundary"] is False and w[1]["boundary"] is True


def test_a_word_that_only_contains_a_filler_is_not_one():
    w = assess.from_assemblyai([{"text": "umbrella", "start": 0, "end": 100}])
    assert w[0]["disfluency"] is False


def test_words_between_uses_the_start_of_each_word():
    w = converted("one two three four five six", pause_every=100)
    assert [x["text"] for x in assess.words_between(w, 0.3, 0.9)] == ["two", "three"]
    assert len(assess.words_between(w, 0.3, None)) == 5


# -- the verdict ----------------------------------------------------------------------------

def test_a_written_answer_gets_a_probe_instruction_with_its_reasons():
    r = assess.assess(converted(WRITTEN, pause_every=9, pause_ms=400), converted(CHATTY), MODEL)
    assert r["verdict"] == "prepared" and r["sounds_prepared"] is True
    assert r["reasons"], r
    assert "exactly one short follow-up" in r["instruction"]
    assert "Never say or hint" in r["instruction"]


def test_a_spontaneous_answer_is_left_alone():
    r = assess.assess(converted(CHATTY_2), converted(CHATTY), MODEL)
    assert r["verdict"] == "spontaneous" and r["sounds_prepared"] is False
    assert "nothing to press on" in r["instruction"] and r["reasons"] == []


def test_the_warm_up_is_never_judged():
    r = assess.assess(converted(CHATTY), None, MODEL)
    assert r["verdict"] == "baseline" and r["sounds_prepared"] is None


@pytest.mark.parametrize("answer, baseline", [
    ("short answer here", CHATTY),        # too short to measure
    (WRITTEN, "fine thanks"),             # nothing to compare against
])
def test_nothing_measured_asks_for_nothing(answer, baseline):
    r = assess.assess(converted(answer), converted(baseline), MODEL)
    assert r["verdict"] == "not_measured" and r["measured"] is False
    assert r["sounds_prepared"] is None and "Do not press them" in r["instruction"]


def test_the_instruction_never_tells_the_candidate_what_was_measured():
    for answer in (WRITTEN, CHATTY_2):
        r = assess.assess(converted(answer, pause_every=9), converted(CHATTY), MODEL)
        assert "read" not in r["instruction"].lower().replace("never say or hint that the answer sounded prepared or read", "")


# -- the next question comes from the candidate, whatever the verdict ---------------

def test_the_quote_is_the_candidates_own_closing_words():
    """Not the agent's summary of them: the transcript, verbatim, from the end."""
    text = " ".join(f"word{i}" for i in range(40))
    quote = assess.quote_of(converted(text))
    assert quote.split() == [f"word{i}" for i in range(40 - assess.QUOTE_WORDS, 40)]


@pytest.mark.parametrize("answer, baseline", [
    (CHATTY, None),                       # the warm-up
    (CHATTY_2, CHATTY),                   # sounds spontaneous
    (WRITTEN, CHATTY),                    # sounds prepared
    ("short answer here", CHATTY),        # nothing measured
])
def test_every_verdict_hands_back_the_candidates_words(answer, baseline):
    """A verdict that only says 'move on' produces the generic next question this
    project exists to remove. Every result carries the words instead."""
    r = assess.assess(converted(answer), converted(baseline) if baseline else None, MODEL)
    tail = " ".join(answer.split()[-6:])
    assert tail in r["instruction"], r["verdict"]
    assert tail in r["quote"]
    assert "word for word inside your next question" in r["instruction"]


def test_an_answer_with_no_words_still_forbids_a_generic_question():
    r = assess.assess([], converted(CHATTY), MODEL)
    assert r["quote"] == ""
    assert "not on a topic heading" in r["instruction"]
    assert "could not have answered before speaking" in r["instruction"]
