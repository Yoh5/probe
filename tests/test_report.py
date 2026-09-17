"""The recruiter's report: what it says, and what it refuses to say."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import report  # noqa: E402
from test_assess import MODEL  # noqa: E402


def words(text, start_ms):
    """Words shaped like a saved answer: milliseconds, in order."""
    out, at = [], start_ms
    for token in text.split():
        out.append({"text": token, "start": at, "end": at + 260})
        at += 300
    return out


def session(**over):
    answer_one = words("I got up early and went to the gym before work", 3000)
    answer_two = words("The first file that broke was the export from the old system", 20000)
    base = {
        "recordedAt": "2026-09-17T09:00:00Z",
        "language": "en",
        "turns": [
            {"role": "interviewer", "text": "What did you do yesterday?", "at": 1000},
            {"role": "candidate", "text": "I got up early...", "at": 9000},
            {"role": "interviewer", "text": "You said the delimiters broke - which file?", "at": 16000},
            {"role": "candidate", "text": "The first file...", "at": 27000},
        ],
        "assessments": [
            {"topic_id": "warmup", "verdict": "baseline", "measured": False, "reasons": [],
             "quote": "before work", "answer_words": answer_one},
            {"topic_id": "project", "verdict": "prepared", "measured": True, "score": 0.9,
             "threshold": -0.2, "reasons": ["longer words than in the warm-up"],
             "quote": "the old system", "answer_words": answer_two},
        ],
    }
    base.update(over)
    return base


def test_the_question_comes_from_the_clock_not_from_counting_turns():
    """The transcription splits one spoken answer into several turns whenever the
    candidate pauses. Counting turns would pair every later answer with the wrong
    question; comparing timestamps cannot drift."""
    noisy = session()
    noisy["turns"].insert(2, {"role": "candidate", "text": "...and then work", "at": 11000})
    built = report.build(noisy, MODEL)
    assert built["answers"][0]["question"] == "What did you do yesterday?"
    assert built["answers"][1]["question"] == "You said the delimiters broke - which file?"


def test_an_answer_with_no_stored_words_admits_it_does_not_know_the_question():
    """Sessions recorded before the answer words were kept cannot be paired. The
    report shows what was assessed and says nothing about which question it was."""
    old = session()
    for assessment in old["assessments"]:
        del assessment["answer_words"]
        assessment["words"] = 31               # the count that used to land under this name
    built = report.build(old, MODEL)
    for answer in built["answers"]:
        assert answer["question"] == ""
        assert answer["excerpt"] is True
        assert answer["said"]                   # the quote taken from the answer itself
    assert built["answers"][0]["facts"]["words"] == 31


def test_the_headline_counts_only_what_could_be_compared():
    built = report.build(session(), MODEL)
    assert built["counts"] == {"answers": 2, "compared": 1, "flagged": 1, "words_spoken": 23}
    assert built["headline"] == "1 of 1 comparable answers sounds prepared."
    assert built["status"] == "flag"


def test_nothing_comparable_is_not_a_pass():
    """An interview with nothing measurable in it says so, and is not reported as
    clear. A clear report and an empty one mean different things."""
    empty = session(assessments=[{"topic_id": "warmup", "verdict": "not_measured",
                                  "quote": "um", "answer_words": []}])
    built = report.build(empty, MODEL)
    assert built["status"] == "none"
    assert "could be compared" in built["headline"]


def test_a_clean_interview_says_so_plainly():
    clean = session()
    clean["assessments"][1].update(verdict="spontaneous", reasons=[])
    built = report.build(clean, MODEL)
    assert built["status"] == "clear"
    assert built["headline"].startswith("None of the 1")


def test_the_facts_are_measured_never_estimated():
    built = report.build(session(), MODEL)
    facts = built["answers"][1]["facts"]
    assert facts["words"] == 12
    assert facts["seconds"] == pytest.approx(3.6, abs=0.1)     # 11 gaps of 300ms, plus one word
    assert facts["words_per_minute"] == round(12 / facts["seconds"] * 60)


def test_a_single_word_answer_has_no_rate_to_report():
    """One word has no duration between words, so there is no rate. Reporting one
    anyway would be inventing a measurement."""
    one = session(assessments=[{"topic_id": "warmup", "verdict": "not_measured", "quote": "yes",
                                "answer_words": words("yes", 0)}])
    facts = report.build(one, MODEL)["answers"][0]["facts"]
    assert facts["seconds"] is None and facts["words_per_minute"] is None


def test_the_limits_quote_the_model_rather_than_a_slogan():
    """Every number in the limits comes from the fitted model, so refitting it
    cannot leave a stale claim behind in the report."""
    lines = " ".join(report.limits(MODEL))
    assert "never whether the candidate is any good at the job" in lines
    assert "never as a reason to reject" in lines


def test_the_limits_survive_a_model_with_no_provenance():
    bare = {"threshold": -0.2, "signals": []}
    lines = report.limits(bare)
    assert lines and all(isinstance(line, str) for line in lines)


def test_the_report_repeats_the_verdict_and_never_recomputes_it():
    """The interview decided; the report reads. A report that scored answers again
    could contradict the interview it describes."""
    odd = session()
    odd["assessments"][1]["verdict"] = "spontaneous"      # disagrees with its own reasons
    built = report.build(odd, MODEL)
    assert built["answers"][1]["verdict"] == "spontaneous"
    assert built["status"] == "clear"
