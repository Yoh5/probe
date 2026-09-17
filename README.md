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
5. The recruiter gets a report that opens on **what to dig into at the next
   interview** — one line per topic, with what the candidate claimed and why it is
   worth thirty more seconds. Underneath it sits the evidence: every answer, what
   was measured, and what the measurement cannot tell them.

Six questions, ninety seconds an answer, about five minutes. Three of the six are
follow-ups, because a follow-up cannot be prepared for and an opening question can.

Two silences, because they mean different things. A sentence that landed gets 2.2
seconds before the interviewer takes its turn; one that trailed off gets nine, out
of the ten the API allows, because that pause is someone hunting for a word and
taking the turn from them is the rudest thing this can do.

## Where the measurement fits

This is the part that is easy to get backwards, so it is worth saying plainly —
and the report shows the whole chain for every answer, so nobody has to take it
on trust:

```
The code measured        1.01x long words   5.0 hesitations
                         0.38x clause breaks   1.74x words between pauses
The code decided         Sounds prepared - fewer run-on clauses than in the warm-up
The code told            "Ask exactly one short follow-up that a script cannot
the interviewer           cover... These are the candidate's own closing words: ..."
The interviewer          "When you were trying to fix that the agent was often
then asked                hallucinating, what was the first thing you tried?"
```

The language model never saw those numbers and never chose that instruction. It
chose the wording of the question.

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
  says what to ask about at the next interview, and stops there. A flag is a
  question to ask, never a reason to reject.
- It does **not tell you whether an answer was true** — only how it was delivered.
- An answer can sound prepared because someone rehearsed, because they have told
  the story fifty times, or because that is simply how they speak. Probe cannot
  tell those apart, and says so on every report it produces.

## What it is worth

A company posting one engineering role gets two or three hundred applications and
ends up with about twenty-five worth qualifying. Today that costs one of two
things.

**A screening call.** Twenty-five conversations of half an hour is twelve and a
half hours of recruiter time for one role, before counting the scheduling and the
people who do not turn up.

**A one-way video round.** Cheap to run and broken in two known ways: the
questions are fixed, so they end up on Glassdoor and the answers come back
rehearsed; and the recruiter still has to watch two hours of video at walking
pace, because video cannot be skimmed, searched or quoted.

What Probe changes:

- **The questions cannot leak, because they do not exist yet.** One is written in
  advance. The rest are made out of what the candidate just said.
- **The output is text.** Two hours of video becomes twenty-five reports that open
  on two lines each - what to dig into - and a transcript that can be searched,
  quoted, and attached to an ATS.
- **The human interview gets better, not skipped.** The recruiter arrives at the
  real conversation already knowing where to press. Thirty minutes of signal
  instead of ten.
- **No scheduling.** The candidate picks the moment.
- **Six languages.** The candidate answers in their own.

For the candidate: five minutes instead of a half-hour call on a Tuesday
afternoon, and a conversation where someone asks about what they actually said.
No camera either - no appearance, no background, no framing. That is one channel
of bias removed, not all of them: a voice still carries an accent.

The strongest case is not filtering people out. **It is finding the ones a CV
hides** - a career change, a school nobody has heard of - who never get the
half-hour call, and who go three questions deep the moment someone asks them
about something they really built.

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

## Deploying it

`render.yaml` is a Render blueprint. The key is `sync: false`, so Render asks for
it in its own dashboard and it never enters the repository.

One setting matters more than it looks: **`PROBE_REGION`**, `us` or `eu`.

AssemblyAI runs the Voice Agent API in two regions, and an agent belongs to the
one it was created in. Left implicit, that region is wherever the caller happens
to be — so a server in Oregon creates its interviewer in the US, a candidate in
Europe looks for it in the EU, and the session is refused with `Agent not found`
while creating the agent answered 201, reading it back answered 200 and minting a
token answered 200. Nothing in any log says otherwise. Whether the interview
starts comes down to the latitude of whoever opens the page.

So set it to the region your candidates are in. `/api/health` reports which one
is live, along with whether the key is present and whole and the status codes
from creating an agent, reading it back and minting a token — booleans and status
codes only, never any part of the key.

Storage is the other choice, and it is a real trade rather than an oversight: a
free instance has no persistent disk, so interviews and the links that produced
them do not survive a redeploy. `render.yaml` says how to move to a paid instance
with one, and ships on free.

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

## What was written before this hackathon

Probe was built for the AssemblyAI Voice Agent Hackathon (1–30 September 2026) and
its git history starts on 16 September. Two files in it were not written during the
hackathon, and they are named here rather than left to be discovered:

| File | Lines | Where it comes from |
|---|---|---|
| `features.py` | 204 | copied unchanged from [Unscripted](https://github.com/Yoh5/unscripted), my own earlier open-source project |
| `detector.py` | 57 | copied unchanged from the same place |
| `detector.json` | — | the fitted model itself: 20 labelled answers from one speaker, frozen on 14 September |

That is 261 of about 3,000 lines. Everything else — the voice loop, the two
AssemblyAI connections, the turn-taking, `assess.py`, `interview.py`, `invites.py`,
`report.py`, the server, both pages and 128 tests — was written for this hackathon.

Unscripted was submitted to a different hackathon. Probe is not a resubmission of
it: Unscripted asks a fixed list of questions and reports afterwards whether the
answers sounded read. Probe uses the same measurement live, inside the
conversation, to decide what to ask next. The shared part is the signal library and
the frozen model, in the way any project shares a library.

## Tests

```bash
python -m pytest -q          # 136
```

Including `tests/test_browser.py`, which runs a whole conversation through the
real page in a headless browser against a fake AssemblyAI, with time sped up
sixty times: the opening, a cough mid-assessment, a candidate who says nothing, a
candidate who never stops, the question limit and the clocks.

Each rule that matters has been broken on purpose to check its test fails.
