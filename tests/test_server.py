"""The routes: the two tokens, the verdict, and saved sessions."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server  # noqa: E402
from test_assess import CHATTY, WRITTEN, aai_words  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "long-lived-secret")
    return TestClient(server.app)


@pytest.fixture
def minted(monkeypatch):
    """Both token calls and the agent creation answered, with the requests recorded."""
    seen = {"tokens": [], "agents": []}

    async def fake_token(client, url, headers, params):
        seen["tokens"].append({"url": url, "headers": headers, "params": params})
        return f"token-for-{'agent' if 'agents' in url else 'streaming'}"

    class FakeResponse:
        status_code = 201

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            seen["agents"].append({"url": url, "headers": headers, "payload": json})
            return FakeResponse({"id": f"agent-{json['input']['language_codes'][0]}"})

    monkeypatch.setattr(server, "_token", fake_token)
    monkeypatch.setattr(server.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(server, "AGENTS", {})
    return seen


# -- starting a session ---------------------------------------------------------------

def test_the_browser_gets_an_agent_id_and_two_tokens(client, minted):
    body = client.post("/api/session", json={"language": "en"}).json()
    assert body == {"agent_id": "agent-en", "agent": "token-for-agent",
                    "streaming": "token-for-streaming", "language": "en",
                    "ttl": server.TOKEN_TTL_SECONDS}


def test_the_long_lived_key_never_reaches_the_browser(client, minted):
    text = client.post("/api/session", json={"language": "en"}).text
    assert "long-lived-secret" not in text
    # The agent endpoint wants a Bearer prefix, the streaming one wants the bare key.
    agent, streaming = minted["tokens"]
    assert agent["headers"]["Authorization"] == "Bearer long-lived-secret"
    assert streaming["headers"]["Authorization"] == "long-lived-secret"


def test_what_the_interviewer_is_told_stays_on_the_server(client, minted):
    """The prompt names what to probe. In the page it would be readable by the
    candidate, so it is stored at AssemblyAI and only its id is handed out."""
    response = client.post("/api/session", json={"language": "en"})
    payload = minted["agents"][0]["payload"]
    assert "assess_answer" in json.dumps(payload["tools"])
    assert "quote their own words" in payload["system_prompt"]
    assert payload["system_prompt"] not in response.text


def test_each_language_gets_its_own_voice_and_is_created_once(client, minted):
    assert client.post("/api/session", json={"language": "fr"}).json()["agent_id"] == "agent-fr"
    client.post("/api/session", json={"language": "fr"})
    client.post("/api/session", json={"language": "en"})
    created = {call["payload"]["input"]["language_codes"][0]: call["payload"]["voice"]["voice_id"]
               for call in minted["agents"]}
    assert created == {"fr": "estelle", "en": "alba"}
    assert len(minted["agents"]) == 2, "the stored agent is reused, not recreated per interview"


def test_a_language_nobody_can_speak_back_is_refused(client, minted):
    r = client.post("/api/session", json={"language": "ar"})
    assert r.status_code == 422 and "ar" in r.json()["detail"]


def test_no_language_means_the_first_one_offered(client, minted):
    assert client.post("/api/session", json={}).json()["language"] == "en"


def test_a_missing_key_is_named(client, monkeypatch):
    monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
    r = client.post("/api/session", json={"language": "en"})
    assert r.status_code == 503 and "ASSEMBLYAI_API_KEY" in r.json()["detail"]


def test_certificate_verification_is_never_disabled():
    assert server.tls_context() is not False


# -- the verdict ---------------------------------------------------------------------------

def test_a_written_answer_comes_back_with_an_instruction(client):
    r = client.post("/api/assess", json={
        "answer_words": aai_words(WRITTEN, pause_every=9, pause_ms=400),
        "baseline_words": aai_words(CHATTY)})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "prepared" and body["sounds_prepared"] is True
    assert "follow-up" in body["instruction"]


def test_the_warm_up_itself_is_not_judged(client):
    body = client.post("/api/assess", json={"answer_words": aai_words(CHATTY), "baseline_words": None}).json()
    assert body["verdict"] == "baseline"


@pytest.mark.parametrize("payload, status", [
    ({}, 422),
    ({"answer_words": "no"}, 422),
    ({"answer_words": [{"text": "hi"}]}, 422),
    ({"answer_words": [], "baseline_words": "no"}, 422),
])
def test_a_malformed_assessment_request_is_refused_with_a_reason(client, payload, status):
    r = client.post("/api/assess", json=payload)
    assert r.status_code == status and r.json()["detail"]


# -- sessions ------------------------------------------------------------------------------------

def test_a_session_round_trips(client):
    saved = client.post("/api/sessions", json={"turns": [{"role": "agent", "text": "Hello"}]})
    assert saved.status_code == 200
    session_id = saved.json()["id"]
    assert server.SESSION_ID.match(session_id)
    assert client.get(f"/api/sessions/{session_id}").json()["turns"][0]["text"] == "Hello"


def test_the_id_is_never_taken_from_the_request(client):
    body = client.post("/api/sessions", json={"id": "../escape", "turns": []}).json()
    assert server.SESSION_ID.match(body["id"])


@pytest.mark.parametrize("bad", ["../secrets", "stray", "20260916T120000Z-zz"])
def test_loading_refuses_anything_but_a_generated_id(client, bad):
    assert client.get(f"/api/sessions/{bad}").status_code == 404


def test_a_session_without_turns_is_refused(client):
    assert client.post("/api/sessions", json={"turns": "none"}).status_code == 422


def test_an_oversized_session_is_refused(client, monkeypatch):
    monkeypatch.setattr(server, "MAX_SESSION_BYTES", 50)
    assert client.post("/api/sessions", json={"turns": [{"text": "x" * 200}]}).status_code == 413


def test_the_page_is_told_the_role_and_the_languages_only(client):
    body = client.get("/api/interview").json()
    assert body["role"] and [l["code"] for l in body["languages"]][:2] == ["en", "fr"]
    # What the interviewer is told to look for is not the candidate's business.
    assert "topics" not in body and "goal" not in json.dumps(body)
