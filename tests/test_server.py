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
    monkeypatch.setattr(server, "INVITES_DIR", tmp_path / "invites")
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "long-lived-secret")
    return TestClient(server.app)


@pytest.fixture
def minted(monkeypatch):
    """Both token calls and the agent creation answered, with the requests recorded.

    `readback` is the status the fake returns when the server fetches the agent it
    just created. A real deployment answered 200 to the creation and then refused
    the session with "Agent not found", so that fetch is what the server does to
    catch it before a candidate does.
    """
    seen = {"tokens": [], "agents": [], "readbacks": [], "readback": 200}

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

        async def get(self, url, headers=None, params=None):
            seen["readbacks"].append({"url": url, "headers": headers})
            found = FakeResponse({"id": url.rsplit("/", 1)[-1]})
            found.status_code = seen["readback"]
            return found

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
    assert "must be built on something they have already said" in payload["system_prompt"]
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


# -- the report the recruiter reads -------------------------------------------------

def saved(client):
    """One interview through the real save route, returning its id."""
    answer = aai_words(WRITTEN, start_ms=12000)
    response = client.post("/api/sessions", json={
        "recordedAt": "2026-09-17T09:00:00Z",
        "language": "en",
        "turns": [
            {"role": "interviewer", "text": "What did you do yesterday?", "at": 1000},
            {"role": "candidate", "text": "I got up early", "at": 9000},
            {"role": "interviewer", "text": "Tell me about a project", "at": 11000},
            {"role": "candidate", "text": WRITTEN, "at": 30000},
        ],
        "assessments": [
            {"topic_id": "warmup", "verdict": "baseline", "quote": "early",
             "answer_words": aai_words(CHATTY, start_ms=2000)},
            {"topic_id": "project", "verdict": "prepared", "measured": True, "score": 1.2,
             "reasons": ["longer words than in the warm-up"], "quote": "defensive programming",
             "answer_words": answer},
        ],
    })
    assert response.status_code == 200
    return response.json()["id"]


def test_a_saved_interview_can_be_read_back_as_a_report(client):
    built = client.get(f"/api/report/{saved(client)}").json()
    assert built["status"] == "flag"
    assert built["answers"][1]["question"] == "Tell me about a project"
    assert built["limits"]


def test_a_report_for_an_interview_that_does_not_exist_is_a_404(client):
    assert client.get("/api/report/20260917T090000Z-deadbeef").status_code == 404


def test_a_report_id_shaped_like_a_path_never_reaches_the_disk(client):
    """The id becomes a file name, so anything that is not an id is refused before
    it is used as one."""
    for bad in ("../server", "..%2Fserver", "x" * 200, "20260917T090000Z-nothex!"):
        assert client.get(f"/api/report/{bad}").status_code == 404


def test_the_list_shows_every_interview_newest_first(client):
    first, second = saved(client), saved(client)
    listed = client.get("/api/sessions").json()["sessions"]
    assert [s["id"] for s in listed] == sorted({first, second}, reverse=True)
    assert all(s["headline"] and s["status"] for s in listed)


def test_a_broken_file_is_skipped_rather_than_breaking_the_list(client):
    saved(client)
    (server.SESSIONS_DIR / "20260917T090000Z-aaaaaaaa.json").write_text("{not json", encoding="utf-8")
    assert len(client.get("/api/sessions").json()["sessions"]) == 1


# -- the question limit -------------------------------------------------------------

def test_the_interview_is_told_to_stop_when_the_questions_run_out(client):
    """The allowance is read from the brief on the server. A browser that says it
    has asked fewer questions than it has cannot buy itself more."""
    limit = server.BRIEF["max_questions"]
    body = {"answer_words": aai_words(WRITTEN), "baseline_words": aai_words(CHATTY), "asked": limit}
    verdict = client.post("/api/assess", json=body).json()
    assert verdict["last"] is True
    assert "call end_interview now" in verdict["instruction"]
    assert verdict["verdict"] == "prepared"      # still measured, still reported


def test_before_the_limit_the_interview_carries_on(client):
    body = {"answer_words": aai_words(WRITTEN), "baseline_words": aai_words(CHATTY), "asked": 1}
    verdict = client.post("/api/assess", json=body).json()
    assert verdict["last"] is False
    assert "end_interview" not in verdict["instruction"]


def test_a_nonsense_question_count_is_refused(client):
    for bad in ("many", -1, 2.5):
        body = {"answer_words": aai_words(WRITTEN), "baseline_words": aai_words(CHATTY), "asked": bad}
        assert client.post("/api/assess", json=body).status_code == 422


# -- the turn detection the interviewer is created with -----------------------------

def test_the_silence_bounds_are_ones_assemblyai_will_accept(client, minted):
    """AssemblyAI requires min_silence STRICTLY below max_silence, and enforces it
    when the socket connects rather than when the agent is created. Equal values
    passed creation and then closed every session with a policy violation: the
    interview would not start at all, and nothing on the server said why."""
    client.post("/api/session", json={"language": "en"})
    detection = minted["agents"][0]["payload"]["input"]["turn_detection"]
    assert 0 < detection["min_silence"] < detection["max_silence"] <= 10000


def test_the_interviewer_waits_about_five_seconds_before_taking_a_turn(client, minted):
    """A pause is thinking, not an ending. Anything much under five seconds steps
    on candidates mid-thought, which is what this was raised from."""
    client.post("/api/session", json={"language": "en"})
    detection = minted["agents"][0]["payload"]["input"]["turn_detection"]
    assert detection["min_silence"] >= 4500
    assert detection["max_silence"] >= 5000


# -- the candidate's own link -------------------------------------------------------

def make_invite(client, label="Amina"):
    response = client.post("/api/invites", json={"label": label})
    assert response.status_code == 200
    return response.json()


def test_an_invitation_comes_back_with_the_link_to_send(client):
    invite = make_invite(client)
    assert invite["path"] == f"/i/{invite['id']}"
    assert invite["status"] == "waiting"
    assert client.get(invite["path"]).status_code == 200      # the page is served there


def test_the_candidates_page_says_whether_the_link_is_still_good(client):
    invite = make_invite(client)
    state = client.get(f"/api/invites/{invite['id']}").json()
    assert state["status"] == "waiting" and state["label"] == "Amina"
    assert "session_id" not in state       # the page is told nothing it has no use for


def test_asking_about_a_link_does_not_spend_it(client, minted):
    invite = make_invite(client)
    client.get(f"/api/invites/{invite['id']}")
    assert client.post("/api/session", json={"language": "en", "invite": invite["id"]}).status_code == 200


def test_an_interview_taken_once_cannot_be_taken_again(client, minted):
    """The whole promise: a second attempt would be an attempt with the questions
    already heard, which is the failure this replaces."""
    invite = make_invite(client)
    assert client.post("/api/session", json={"language": "en", "invite": invite["id"]}).status_code == 200
    saved = client.post("/api/sessions", json={"turns": [], "invite": invite["id"]})
    assert saved.status_code == 200

    refused = client.post("/api/session", json={"language": "en", "invite": invite["id"]})
    assert refused.status_code == 409
    assert "already been taken" in refused.json()["detail"]
    assert client.get(f"/api/invites/{invite['id']}").json()["status"] == "done"


def test_the_finished_interview_is_attached_to_the_invitation(client, minted):
    invite = make_invite(client)
    client.post("/api/session", json={"language": "en", "invite": invite["id"]})
    session_id = client.post("/api/sessions", json={"turns": [], "invite": invite["id"]}).json()["id"]
    listed = client.get("/api/invites").json()["invites"]
    assert listed[0]["session_id"] == session_id
    assert client.get(f"/api/report/{session_id}").status_code == 200


def test_an_invitation_that_does_not_exist_is_a_404(client, minted):
    assert client.get("/api/invites/" + "a" * 32).status_code == 404
    assert client.post("/api/session", json={"language": "en", "invite": "a" * 32}).status_code == 404


def test_an_invitation_id_shaped_like_a_path_never_reaches_the_disk(client):
    for bad in ("../server", "..%2Fserver", "nothex", "a" * 200):
        assert client.get(f"/api/invites/{bad}").status_code == 404


def test_an_interview_taken_without_a_link_still_works(client, minted):
    """A recruiter trying out their own interview has no invitation, and should
    not need one."""
    assert client.post("/api/session", json={"language": "en"}).status_code == 200
    assert client.post("/api/sessions", json={"turns": []}).status_code == 200


def test_an_interview_is_saved_even_if_its_invitation_has_vanished(client, minted):
    """The interview happened. Losing the recording because the paperwork went
    missing would be the wrong trade."""
    saved = client.post("/api/sessions", json={"turns": [], "invite": "b" * 32})
    assert saved.status_code == 200
    assert client.get(f"/api/report/{saved.json()['id']}").status_code == 200


def test_the_data_folder_can_be_moved_off_the_container(monkeypatch, tmp_path):
    """A hosted instance writes to a mounted disk. Without that, a link sent to a
    candidate stops working the next time anything ships, because the container's
    own filesystem is wiped on every deploy."""
    monkeypatch.setenv("PROBE_DATA", str(tmp_path))
    import importlib
    reloaded = importlib.reload(server)
    try:
        assert reloaded.SESSIONS_DIR == tmp_path / "sessions"
        assert reloaded.INVITES_DIR == tmp_path / "invites"
    finally:
        monkeypatch.delenv("PROBE_DATA")
        importlib.reload(server)


def test_an_interviewer_that_cannot_be_found_again_is_never_handed_out(client, minted):
    """This is what a real deployment did: 200 to the creation, and then "Agent not
    found" the moment the socket opened. The page cannot explain that and cannot
    recover from it - the candidate sees an interview that will not start while the
    server log says everything is fine. It is caught here instead."""
    minted["readback"] = 404
    refused = client.post("/api/session", json={"language": "en"})
    assert refused.status_code == 502
    assert "cannot find again" in refused.json()["detail"]
    assert "ASSEMBLYAI_API_KEY" in refused.json()["detail"]


def test_the_agent_is_read_back_with_the_key_that_made_it(client, minted):
    client.post("/api/session", json={"language": "en"})
    assert minted["readbacks"][0]["url"].endswith("/agent-en")
    assert minted["readbacks"][0]["headers"]["Authorization"] == "long-lived-secret"
