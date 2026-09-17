"""Probe - what the interview is about, and in which language it is held.

The agent is not given a list of questions to read out. It is given topics and,
for each one, what the recruiter wants to come away with. It asks its own
opening question, then every question after that has to come from what the
candidate just said. A read-out list is exactly what this project is trying to
get past: a candidate can prepare for a known question, and an interviewer who
only reads never notices.

The file is checked when the server starts, so a mistake stops it with a
sentence naming the problem instead of producing an interview with nothing to
ask.
"""
from __future__ import annotations

import json
from pathlib import Path

# Input languages AssemblyAI recognises AND can speak back. Arabic, Hindi and
# the others are recognised but have no voice, so they are not offered: an
# interview the candidate cannot hear back is not an interview.
LANGUAGES = {
    "en": {"name": "English", "voice": "alba"},
    "fr": {"name": "Français", "voice": "estelle"},
    "es": {"name": "Español", "voice": "lola"},
    "de": {"name": "Deutsch", "voice": "juergen"},
    "it": {"name": "Italiano", "voice": "giovanni"},
    "pt": {"name": "Português", "voice": "rafael"},
}

MIN_TOPICS = 1
MAX_TOPICS = 6
MAX_TEXT = 400


class InterviewError(ValueError):
    pass


def validate(data: object) -> dict:
    """The interview brief, cleaned, or InterviewError with the first problem."""
    if not isinstance(data, dict):
        raise InterviewError("the file must be an object")
    unknown = set(data) - {"role", "warmup", "topics", "max_followups", "max_questions", "languages"}
    if unknown:
        raise InterviewError(f"unknown fields: {', '.join(sorted(unknown))}")

    role = data.get("role")
    if not isinstance(role, str) or not role.strip():
        raise InterviewError("role must say what the interview is for")

    warmup = data.get("warmup")
    if not isinstance(warmup, str) or not warmup.strip():
        raise InterviewError("warmup must be the one question asked word for word")
    if len(warmup) > MAX_TEXT:
        raise InterviewError(f"warmup is longer than {MAX_TEXT} characters; it is spoken aloud")

    topics = data.get("topics")
    if not isinstance(topics, list) or not MIN_TOPICS <= len(topics) <= MAX_TOPICS:
        raise InterviewError(f"there must be between {MIN_TOPICS} and {MAX_TOPICS} topics")
    cleaned = []
    for number, topic in enumerate(topics, start=1):
        where = f"topic {number}"
        if not isinstance(topic, dict):
            raise InterviewError(f"{where} must be an object")
        extra = set(topic) - {"id", "goal"}
        if extra:
            raise InterviewError(f"{where} has unknown fields: {', '.join(sorted(extra))}")
        if not isinstance(topic.get("id"), str) or not topic["id"].strip():
            raise InterviewError(f"{where} needs an id")
        goal = topic.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            raise InterviewError(f"{where} needs a goal: what the recruiter wants to come away with")
        if len(goal) > MAX_TEXT:
            raise InterviewError(f"{where} goal is longer than {MAX_TEXT} characters")
        cleaned.append({"id": topic["id"].strip(), "goal": " ".join(goal.split())})
    if len({t["id"] for t in cleaned}) != len(cleaned):
        raise InterviewError("two topics share an id")

    follow_ups = data.get("max_followups", 2)
    if not isinstance(follow_ups, int) or isinstance(follow_ups, bool) or not 1 <= follow_ups <= 4:
        raise InterviewError("max_followups must be a whole number between 1 and 4")

    limit = data.get("max_questions", 8)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 2 <= limit <= 20:
        raise InterviewError("max_questions must be a whole number between 2 and 20")
    if limit <= len(cleaned):
        raise InterviewError(f"max_questions ({limit}) leaves no room for {len(cleaned)} topics "
                             "plus the warm-up")

    offered = data.get("languages", list(LANGUAGES))
    if not isinstance(offered, list) or not offered:
        raise InterviewError("languages must be a non-empty list")
    unknown_languages = [code for code in offered if code not in LANGUAGES]
    if unknown_languages:
        raise InterviewError(f"no voice speaks {', '.join(unknown_languages)}; "
                             f"choose from {', '.join(LANGUAGES)}")

    return {"role": role.strip(), "warmup": " ".join(warmup.split()), "topics": cleaned,
            "max_followups": follow_ups, "max_questions": limit,
            "languages": [{"code": code, **LANGUAGES[code]} for code in offered]}


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise InterviewError(f"{path.name} could not be read: {error.strerror}") from None
    except ValueError as error:
        raise InterviewError(f"{path.name} is not valid JSON: {error}") from None
    try:
        return validate(data)
    except InterviewError as error:
        raise InterviewError(f"{path.name}: {error}") from None


def voice_for(code: str, brief: dict) -> str:
    for language in brief["languages"]:
        if language["code"] == code:
            return language["voice"]
    return brief["languages"][0]["voice"]


def system_prompt(brief: dict, language_code: str) -> str:
    """What the agent is told. The rules here are what makes it an interviewer
    rather than a form: one opening question per topic, and every question after
    that built on the candidate's own words."""
    language = next((l for l in brief["languages"] if l["code"] == language_code), brief["languages"][0])
    topics = "\n".join(f"- {t['id']}: {t['goal']}" for t in brief["topics"])
    return "\n".join([
        f"You are interviewing a candidate for this role: {brief['role']}.",
        f"Speak {language['name']} for the whole interview, including the first sentence.",
        "",
        "How the interview runs:",
        f"1. Open with this warm-up question, translated into {language['name']} but otherwise unchanged: "
        f"\"{brief['warmup']}\" Let them answer fully. It is small talk; do not dig into it.",
        "2. Then cover these topics, one at a time, in order. Each one is written as what you need to "
        "come away KNOWING. It is not a question, and it is never to be read out:",
        topics,
        "",
        "How you ask:",
        "- The warm-up is the only question you may ask without having heard the candidate. Every single "
        "question after it, including the one that opens a new topic, must be built on something they have "
        "already said.",
        "- Building on it means this: repeat a phrase of theirs word for word inside your question, then ask "
        "for what only the person who lived it would know. A concrete number, the first thing that broke, "
        "what they chose not to do, who disagreed, how they found out they were wrong.",
        "- Before you speak, check your question against this test: could the candidate have answered it if "
        "they had been handed it a week ago? If yes, it is the wrong question - rewrite it around their words. "
        "A topic is a direction to steer in, never a question to read out.",
        "- Do not announce the topic, and do not say 'let us move on to'. Walk across by way of what they said.",
        "- A topic's goal turned into a question is the worst question you can ask. \"Tell me about a project "
        "you owned end to end\" is the goal read aloud: it is the question every candidate has already "
        "rehearsed, and asking it wastes the topic. Instead, find the smallest concrete thing the candidate "
        "has already named - a tool, a week, a person, a number, a place - and ask about that thing. The topic "
        "is where you steer to over the next few turns, not what you announce.",
        "- If nothing they have said leads anywhere near the topic, ask about the last specific thing they "
        "named anyway, and steer from their answer. One extra turn is cheaper than a rehearsed one.",
        "- Never ask the same question twice, even reworded. If the candidate has not started answering, they "
        "are thinking: say nothing and wait for them.",
        "- Most of your questions should be follow-ups. A follow-up cannot be prepared for; the question that "
        "opens a topic can.",
        "- One question at a time. Never stack two questions in one turn.",
        f"- Stay on a topic for at most {brief['max_followups']} follow-ups, then move on, even if unsatisfied.",
        f"- The whole interview is {brief['max_questions']} questions, warm-up included. Spend them: do not "
        "linger on one topic until there is nothing left for the others. You will be told when the last one "
        "has been asked.",
        "",
        "The tool:",
        f"- After every candidate answer, call assess_answer with the topic id and one line, in "
        f"{language['name']}, saying what they claimed - it is quoted back to the recruiter. Wait for the result before speaking. This holds even when the answer was short, off topic, "
        "or you plan to ask the question again.",
        "- The result carries an instruction and, with it, the candidate's own closing words as the "
        "transcript recorded them. Follow the instruction exactly and use those words: they are what your "
        "next question is made of.",
        "- Never mention the tool, a score, an assessment, or that an answer sounded prepared or read. Never tell "
        "the candidate how they are doing.",
        "",
        "How you listen: a pause is thinking, not an ending. Once you have asked a question, say nothing "
        "until the candidate has answered it, however long they take to start. Never fill a silence, never "
        "prompt someone who has gone quiet, and never repeat or rephrase a question because the answer is "
        "slow in coming. They can see how long they have. Wait.",
        "",
        "How you sound: warm, curious, and brief. Under two sentences per turn. No compliments, no summaries of "
        "what they just said, no 'great question'. When the last topic is done, thank them in one sentence and "
        "call end_interview.",
    ])
