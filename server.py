"""Probe - the server.

It does three things, and never touches the audio:

1. serves the interview and report pages;
2. mints the two short-lived AssemblyAI tokens the browser needs - one for the
   Voice Agent API, one for Realtime speech-to-text - so the API key stays here;
3. answers `assess_answer`: the browser sends the words of the answer that just
   ended, this computes the verdict (assess.py) and returns the instruction the
   agent follows.

The audio goes straight from the browser to AssemblyAI, in two parallel
connections fed by the same microphone: the agent connection carries the
conversation, the streaming connection carries the word timings the verdict
rests on.

Run: uvicorn server:app --port 8000
"""
from __future__ import annotations

import json
import os
import re
import secrets
import ssl
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import assess
import detector
import interview
import report

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

SESSIONS_DIR = ROOT / "sessions"
MAX_SESSION_BYTES = 4_000_000
SESSION_ID = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")

AGENTS_URL = "https://agents.assemblyai.com/v1/agents"
AGENT_TOKEN_URL = "https://agents.assemblyai.com/v1/token"
STREAMING_TOKEN_URL = "https://streaming.assemblyai.com/v3/token"
# Long enough to open both sockets, short enough that a token lifted from the
# page is worthless. Tokens are single-use: one interview, one fetch.
TOKEN_TTL_SECONDS = 120
MAX_SESSION_SECONDS = 1800

BRIEF = interview.load(Path(os.environ.get("PROBE_INTERVIEW", ROOT / "interview.json")))
MODEL = detector.load()

# One stored agent per language, created on first use and kept for the life of the
# process. Storing it at AssemblyAI keeps the prompt - what the interviewer is told
# to probe - out of the candidate's browser, where it would be readable.
AGENTS: dict[str, str] = {}


def tls_context():
    """Validate certificates against the operating system's trust store.

    Verification stays fully on; only the list of trusted roots changes. An
    antivirus that scans HTTPS re-signs every site with a root installed in the
    OS store, which certifi does not know about.
    """
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return True


app = FastAPI(title="Probe")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/report")
def report_page() -> FileResponse:
    return FileResponse(ROOT / "static" / "report.html")


@app.get("/reports")
def reports_page() -> FileResponse:
    return FileResponse(ROOT / "static" / "reports.html")


@app.get("/api/interview")
def brief() -> dict:
    """What the page may show: the role, the languages, and how many parts there are.

    How many, and never which: the count lets the page say where the candidate has
    got to, while the topics themselves stay on the server. A candidate who could
    read them could prepare for them, which is the whole thing this interview is
    built to see through.
    """
    return {"role": BRIEF["role"], "languages": BRIEF["languages"],
            "parts": len(BRIEF["topics"]) + 1}


async def _token(client: httpx.AsyncClient, url: str, headers: dict, params: dict) -> str:
    try:
        response = await client.get(url, headers=headers, params=params)
    except httpx.HTTPError as error:
        raise HTTPException(502, f"AssemblyAI unreachable: {type(error).__name__}")
    if response.status_code >= 400:
        # The status is enough to tell a bad key (401) from an outage; the body
        # can echo request details back.
        raise HTTPException(502, f"AssemblyAI refused the token request ({response.status_code})")
    token = response.json().get("token")
    if not token:
        raise HTTPException(502, "AssemblyAI answered without a token")
    return token


TOOLS = [
    {
        "name": "assess_answer",
        "description": "Call this after every single candidate answer, before you say anything at all - "
                       "including before repeating or rephrasing a question. It returns the instruction "
                       "you must follow next. Never speak twice in a row without calling it.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic_id": {"type": "string", "description": "The topic they were answering, or 'warmup'"},
                "claim": {"type": "string", "description": "One line: what the candidate claimed"},
            },
            "required": ["topic_id", "claim"],
        },
        "execution_mode": "interactive",
        "timeout_seconds": 20,
    },
    {
        "name": "end_interview",
        "description": "Call this once the last topic is done and you have thanked the candidate.",
        "parameters": {"type": "object", "properties": {}},
        "execution_mode": "interactive",
        "timeout_seconds": 10,
    },
]


async def _agent_id(client: httpx.AsyncClient, key: str, language: str) -> str:
    """The stored agent for this language, created once."""
    if language in AGENTS:
        return AGENTS[language]
    payload = {
        "name": f"Probe interviewer ({language})",
        "system_prompt": interview.system_prompt(BRIEF, language),
        "voice": {"voice_id": interview.voice_for(language, BRIEF)},
        "tools": TOOLS,
        "input": {
            # Five seconds of silence before the interviewer takes the turn,
            # whether or not the answer sounded finished. An interview answer has
            # thinking pauses in it, and a pause is not an ending: at 2.4 s the
            # interviewer was stepping on people mid-thought, which is the one
            # thing that makes an interview feel like a form.
            # AssemblyAI requires min_silence STRICTLY below max_silence, and
            # rejects the session at connect time - not at agent creation - when it
            # is not. Equal values passed creation and then closed every socket
            # with a policy violation, so the interview would not start at all.
            "turn_detection": {"min_silence": 4800, "max_silence": 5000, "interrupt_response": True},
            "language_codes": [language],
        },
    }
    try:
        response = await client.post(AGENTS_URL, headers={"Authorization": key}, json=payload)
    except httpx.HTTPError as error:
        raise HTTPException(502, f"AssemblyAI unreachable: {type(error).__name__}")
    if response.status_code >= 400:
        raise HTTPException(502, f"AssemblyAI refused the interviewer ({response.status_code})")
    agent_id = response.json().get("id")
    if not agent_id:
        raise HTTPException(502, "AssemblyAI answered without an agent id")
    AGENTS[language] = agent_id
    return agent_id


@app.post("/api/session")
async def session(request: Request) -> dict:
    """Everything the page needs to open both connections, and nothing else.

    The interviewer itself - its prompt, its tools, its voice - is stored at
    AssemblyAI under an id. The browser gets the id and two single-use tokens.
    """
    key = os.environ.get("ASSEMBLYAI_API_KEY", "")
    if not key:
        raise HTTPException(503, "ASSEMBLYAI_API_KEY is not set on the server")
    try:
        body = await request.json()
    except ValueError:
        body = {}
    language = (body or {}).get("language", BRIEF["languages"][0]["code"])
    if language not in {offered["code"] for offered in BRIEF["languages"]}:
        raise HTTPException(422, f"this interview is not offered in {language}")

    async with httpx.AsyncClient(timeout=20, verify=tls_context()) as client:
        agent_id = await _agent_id(client, key, language)
        agent = await _token(client, AGENT_TOKEN_URL, {"Authorization": f"Bearer {key}"},
                             {"expires_in_seconds": TOKEN_TTL_SECONDS,
                              "max_session_duration_seconds": MAX_SESSION_SECONDS})
        streaming = await _token(client, STREAMING_TOKEN_URL, {"Authorization": key},
                                 {"expires_in_seconds": TOKEN_TTL_SECONDS})
    return {"agent_id": agent_id, "agent": agent, "streaming": streaming,
            "language": language, "ttl": TOKEN_TTL_SECONDS}


@app.post("/api/assess")
async def assess_answer(request: Request) -> dict:
    """The verdict for the answer that just ended, as the agent's tool result.

    The browser sends the AssemblyAI words of the answer and of the warm-up. The
    decision is made here, in tested code, never by the model conducting the
    interview.
    """
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be an object")
    words = body.get("answer_words")
    baseline = body.get("baseline_words")
    if not isinstance(words, list) or not all(isinstance(w, dict) for w in words):
        raise HTTPException(422, "answer_words must be a list of words")
    if baseline is not None and not isinstance(baseline, list):
        raise HTTPException(422, "baseline_words must be a list of words or null")
    try:
        answer = assess.from_assemblyai(words)
        base = assess.from_assemblyai(baseline) if baseline else None
    except (KeyError, TypeError, ValueError):
        raise HTTPException(422, "each word needs text, start and end")
    asked = body.get("asked")
    if asked is not None and (not isinstance(asked, int) or isinstance(asked, bool) or asked < 0):
        raise HTTPException(422, "asked must be a whole number of questions")
    # The browser says how many questions have been asked; how many are allowed is
    # read here, from the brief, where the candidate cannot reach it.
    return assess.assess(answer, base, MODEL, asked=asked, limit=BRIEF["max_questions"])


@app.post("/api/sessions")
async def save_session(request: Request) -> dict:
    raw = await request.body()
    if len(raw) > MAX_SESSION_BYTES:
        raise HTTPException(413, "session too large")
    try:
        session = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "session is not valid JSON")
    if not isinstance(session, dict) or not isinstance(session.get("turns"), list):
        raise HTTPException(422, "a session needs a list of turns")

    # The id is built here, never taken from the request: it becomes a file name.
    session_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
    SESSIONS_DIR.mkdir(exist_ok=True)
    (SESSIONS_DIR / f"{session_id}.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    return {"id": session_id}


def _read_session(session_id: str) -> dict:
    # The id reaches a file path, so its shape is checked before anything else.
    if not SESSION_ID.match(session_id):
        raise HTTPException(404, "no such session")
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.is_file():
        raise HTTPException(404, "no such session")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/sessions")
def list_sessions() -> dict:
    """Every saved interview, newest first, with just enough to choose one."""
    if not SESSIONS_DIR.is_dir():
        return {"sessions": []}
    found = []
    for path in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        if not SESSION_ID.match(path.stem):
            continue
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue    # a half-written file is skipped, never fatal to the list
        built = report.build(saved, MODEL)
        found.append({"id": path.stem, "recorded_at": built["recorded_at"],
                      "language": built["language"], "headline": built["headline"],
                      "status": built["status"], "counts": built["counts"]})
    return {"sessions": found}


@app.get("/api/sessions/{session_id}")
def load_session(session_id: str) -> dict:
    return _read_session(session_id)


@app.get("/api/report/{session_id}")
def build_report(session_id: str) -> dict:
    """The recruiter's report for one interview.

    Every verdict in it was computed while the interview was running. Nothing is
    judged again here, so a report cannot disagree with the interview it describes.
    """
    return report.build(_read_session(session_id), MODEL)
