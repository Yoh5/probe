"""The report speaks the language the interview was held in."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import interview  # noqa: E402
import report  # noqa: E402
import strings  # noqa: E402

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def test_every_language_the_interview_offers_can_be_reported_in():
    """A candidate who can take the interview in a language must be able to have it
    reported in that language, or the offer was half an offer."""
    assert set(interview.LANGUAGES) <= set(strings.STRINGS)


def test_no_language_is_missing_a_single_string():
    """The page holds no words of its own, so a key missing here is a blank on the
    screen rather than an English fallback nobody notices."""
    expected = set(strings.STRINGS["en"])
    for code, table in strings.STRINGS.items():
        assert set(table) == expected, code


def test_the_placeholders_match_english_everywhere():
    """A translation that drops {n} silently loses a number; one that invents a
    placeholder raises KeyError in front of a recruiter."""
    for key, english in strings.STRINGS["en"].items():
        wanted = set(PLACEHOLDER.findall(english))
        for code, table in strings.STRINGS.items():
            assert set(PLACEHOLDER.findall(table[key])) == wanted, f"{code}/{key}"


def test_nothing_is_left_untranslated_by_copy_paste():
    """Every language must differ from English on the sentences that carry meaning.
    A block pasted from English and never translated passes every other test."""
    carriers = ["head_clear", "limit_notes", "step_missed", "verdict_prepared", "dig"]
    for code, table in strings.STRINGS.items():
        if code == "en":
            continue
        for key in carriers:
            assert table[key] != strings.STRINGS["en"][key], f"{code}/{key}"


def test_every_signal_has_a_name_a_unit_and_a_reason():
    for name in strings.SIGNAL_KINDS:
        for code, table in strings.STRINGS.items():
            assert table[f"signal_{name}"], f"{code}/{name}"
            assert table[f"reason_{name}"], f"{code}/{name}"


def test_the_signals_are_the_ones_the_detector_actually_uses():
    """A signal renamed in the model and not here would be reported under a name
    that no longer means anything."""
    import detector
    assert set(strings.SIGNAL_KINDS) == set(detector.EXPLANATIONS)


@pytest.mark.parametrize("language", sorted(strings.STRINGS))
def test_a_report_comes_back_whole_in_every_language(language):
    session = {
        "language": language,
        "turns": [{"role": "interviewer", "text": "Q", "at": 0},
                  {"role": "candidate", "text": "A", "at": 1000}],
        "assessments": [{"topic_id": "project", "verdict": "prepared", "measured": True,
                         "question": "Q", "claim": "c", "instruction": "i",
                         "pointed": ["mean_run/base"],
                         "signals": {"long_word_share/base": 2.0, "disfluency_rate": 1.0,
                                     "comma_rate/base": 0.5, "mean_run/base": 1.5},
                         "answer_words": [{"text": "a", "start": 0, "end": 100}]}],
    }
    built = report.build(session, None, {"topics": [{"id": "project", "goal": "g"}]})
    assert built["labels"]["report_title"] == strings.STRINGS[language]["report_title"]
    assert built["headline"] == strings.STRINGS[language]["head_one"]
    assert built["answers"][0]["title"] == strings.STRINGS[language]["verdict_prepared"]
    assert built["answers"][0]["reasons"] == [strings.STRINGS[language]["reason_mean_run/base"]]
    assert built["limits"][0] == strings.STRINGS[language]["limit_delivery"]
    assert "{" not in built["headline"] and "{" not in built["limits"][-1]


def test_an_unknown_language_falls_back_to_english_rather_than_to_blanks():
    built = report.build({"language": "zz", "turns": [], "assessments": []})
    assert built["labels"]["report_title"] == strings.STRINGS["en"]["report_title"]
