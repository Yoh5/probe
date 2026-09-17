# Probe

**The one-way video interview asks everyone the same questions. Probe asks one.**

Probe replaces the asynchronous video questionnaire — HireVue, Spark Hire, a form
with a webcam. Those are convenient for exactly one reason and broken for exactly
one reason, and it is the same reason: the questions are fixed, so every candidate
gets the same ones, so the questions circulate, so the answers arrive rehearsed.
A recruiter ends up watching twenty takes of a prepared speech.

Probe is the same convenience without that. A candidate opens a link and talks for
five minutes. One question is written in advance. Every question after it is built
out of what the candidate has just said — their own words quoted back, and then a
request for what only the person who lived it would know. There is nothing to
circulate, because the interview does not exist until they speak.

Built on the [AssemblyAI Voice Agent API](https://www.assemblyai.com/docs), with a
second Realtime Streaming connection carrying the word-level timings the
measurement rests on.

---

## What it actually does

1. A candidate opens a link and talks. No download, no scheduling, six languages.
2. The interviewer asks a warm-up question and listens. It waits five seconds of
   real silence before taking a turn: a pause is thinking, not an ending.
3. After every answer, **code** — not the language model — measures how that
   answer was delivered against the candidate's own warm-up, and hands the
   interviewer one instruction for what to do next.
4. The interviewer follows it, and asks its next question out of the candidate's
   own words.
5. The recruiter gets a report: what was asked, what was said, what was measured,
   and what the measurement cannot tell them.

Six questions, ninety seconds an answer, about five minutes. Three of the six are
follow-ups, because a follow-up cannot be prepared for and an opening question can.

## Where the measurement fits

This is the part that is easy to get backwards, so it is worth saying plainly.

**The measurement is the interviewer's ear, not the product.** Probe is not a
detector with an interview attached; it is an interview that listens to how it is
being answered and changes what it asks next. An answer that sounds rehearsed
earns a follow-up a script cannot cover — a concrete number, the first thing that
broke, who disagreed. An answer that sounds thought up on the spot is left alone
and the interview moves on. The candidate is never told, never scored out loud,
and never judged by the model conducting the interview.

The signal detector itself came from an earlier project of mine,
[Unscripted](https://github.com/Yoh5/unscripted), which asked a fixed list of
questions and reported afterwards whether the answers sounded read. Probe is the
opposite arrangement: the same measurement, used live, to decide what to ask.
Unscripted tells you afterwards. Probe does something about it during.

## What it is not

- It is **not a proctor**. It does not watch a camera, lock a browser, or claim to
  catch cheating. Reading from notes is not misconduct.
- It does **not score candidates**, rank them, or recommend a decision. The report
  says what to ask about at the next interview, and stops there.
- It does **not tell you whether an answer was true** — only how it was delivered.
- An answer can sound prepared because someone rehearsed, because they have told
  the story fifty times, or because that is simply how they speak. Probe cannot
  tell those apart, and says so on every report it produces.

## Who it is for

A team screening more applicants than it has interviewer-hours, that has tried the
one-way video round and found it produced twenty recordings of the same prepared
answer. Probe sits in the same slot in the funnel — before any human time is
spent — and comes back with a transcript worth reading and a short list of what to
dig into if the candidate goes through.

One job posting is one brief. One candidate is one link, and the link works once:
a candidate who could take the interview twice could prepare for the second one,
which would put us back where the video questionnaire is.

---

## Running it

```bash
pip install -r requirements.txt
echo ASSEMBLYAI_API_KEY=... > .env        # never committed
uvicorn server:app --port 8000
```

| Page | What it is |
|---|---|
| `/reports` | the recruiter's page: make a candidate link, see who has taken it |
| `/i/<id>` | a candidate's own link, good for one interview |
| `/report?id=…` | one interview's report |
| `/` | the interview with no invitation, for trying it out yourself |

The interview itself is `interview.json`: the role, the warm-up question asked
word for word, the topics with what the recruiter wants to come away with, the
follow-up budget and the question limit. It is validated at startup, so a mistake
stops the server with a sentence naming the problem instead of producing an
interview with nothing to ask.

## How it is put together

| File | What it holds |
|---|---|
| `server.py` | the routes, the two short-lived AssemblyAI tokens, the stored agent |
| `interview.py` | the brief, validated, and the system prompt built from it |
| `assess.py` | the verdict for one answer, and the instruction the interviewer follows |
| `features.py`, `detector.py` | the signals and the frozen model behind that verdict |
| `report.py` | the recruiter's report, built from the saved session |
| `invites.py` | one candidate, one link, spent when the interview is taken |
| `static/app.js` | the two websockets, the microphone, the turn-taking, the clocks |

The API key never reaches the browser: the page is handed an agent id and two
single-use tokens that expire in two minutes. The topics stay on the server —
a candidate who could read them could prepare for them.

## Tests

```bash
python -m pytest -q          # 119
```

Including `tests/test_browser.py`, which runs a whole conversation through the
real page in a headless browser against a fake AssemblyAI, with time sped up
sixty times: the opening, a cough mid-assessment, a candidate who says nothing, a
candidate who never stops, the question limit and the clocks.

Each rule that matters has been broken on purpose to check its test fails.
