"""Check both AssemblyAI APIs end to end before building on them.

What it proves, with a synthesized voice clip instead of a microphone:

1. both temporary-token endpoints answer (only the HTTP status is printed);
2. Realtime STT (Universal-3.5 Pro) returns word timings, and whether filler
   words such as "um" and repeated words survive in the transcript - the whole
   detector rests on them;
3. the Voice Agent API accepts an inline session with a client-side tool, hears
   the same clip, and calls the tool when told to.

The API key is read from .env and never printed.

Run: python scripts/spike.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import ssl
import subprocess
import sys
import time
import wave
from pathlib import Path

import httpx
import websockets
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
KEY = os.environ.get("ASSEMBLYAI_API_KEY", "")
RATE = 24000
CLIP = ROOT / "scripts" / "spike_clip.wav"
TEXT = ("Um, so, I think, I think the hardest part was, uh, the deadline. "
        "We had two weeks and the, the database migration kept failing.")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def tls():
    # The OS trust store, as in Unscripted: an antivirus that re-signs HTTPS breaks certifi.
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


def make_clip() -> None:
    if CLIP.exists():
        return
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.SelectVoice('Microsoft Zira Desktop');"
        f"$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo({RATE}, 16, 1);"
        f"$s.SetOutputToWaveFile('{CLIP}', $f);"
        f"$s.Speak('{TEXT}'); $s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)


def pcm() -> bytes:
    with wave.open(str(CLIP)) as w:
        assert w.getframerate() == RATE and w.getsampwidth() == 2 and w.getnchannels() == 1
        return w.readframes(w.getnframes())


async def check_tokens() -> None:
    async with httpx.AsyncClient(verify=tls(), timeout=20) as c:
        r = await c.get("https://agents.assemblyai.com/v1/token", params={"expires_in_seconds": 60},
                        headers={"Authorization": f"Bearer {KEY}"})
        print("voice agent token  :", r.status_code, "token present" if r.is_success and r.json().get("token") else r.text[:120])
        r = await c.get("https://streaming.assemblyai.com/v3/token", params={"expires_in_seconds": 60},
                        headers={"Authorization": KEY})
        print("streaming token    :", r.status_code, "token present" if r.is_success and r.json().get("token") else r.text[:120])


async def check_stt(audio: bytes) -> None:
    url = ("wss://streaming.assemblyai.com/v3/ws?speech_model=universal-3-5-pro"
           f"&sample_rate={RATE}&encoding=pcm_s16le&format_turns=true")
    async with websockets.connect(url, additional_headers={"Authorization": KEY}, ssl=tls()) as ws:
        begin = json.loads(await ws.recv())
        print("\nSTT Begin model    :", begin.get("configuration", {}).get("model"), begin.get("type"))

        async def send():
            step = RATE // 20 * 2  # 50 ms of 16-bit samples
            for i in range(0, len(audio), step):
                await ws.send(audio[i:i + step])
                await asyncio.sleep(0.05)
            await ws.send(b"\x00" * RATE * 2)  # a second of silence so the turn can end
            await asyncio.sleep(1.5)
            await ws.send(json.dumps({"type": "Terminate"}))

        sender = asyncio.create_task(send())
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "Turn" and msg.get("end_of_turn"):
                print("STT final turn     :", msg.get("transcript"))
                print("formatted          :", msg.get("turn_is_formatted"))
                for w in msg.get("words", [])[:14]:
                    print(f"   {w.get('start'):>6}-{w.get('end'):<6} {w.get('confidence', 0):.2f} {w.get('text')}")
            elif msg.get("type") in ("Termination", "Error"):
                print("STT", msg.get("type"), {k: v for k, v in msg.items() if k != "type"})
                break
        await sender


async def check_agent(audio: bytes) -> None:
    tools = [{
        "type": "function",
        "name": "assess_answer",
        "description": "Call this right after the candidate finishes answering, before you reply.",
        "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
        "execution_mode": "interactive",
        "timeout_seconds": 20,
    }]
    async with websockets.connect("wss://agents.assemblyai.com/v1/ws",
                                  additional_headers={"Authorization": f"Bearer {KEY}"}, ssl=tls()) as ws:
        await ws.send(json.dumps({"type": "session.update", "session": {
            "system_prompt": "You are a job interviewer. When the candidate finishes an answer, call assess_answer, then ask one short follow-up question.",
            "greeting": "Tell me about a hard project.",
            "tools": tools,
            "output": {"voice": "alba"},
        }}))
        started, last, pending, sent_audio = time.monotonic(), None, [], False
        audio_bytes = 0
        async for raw in ws:
            msg = json.loads(raw)
            t = msg.get("type")
            if t == "reply.audio":
                audio_bytes += len(base64.b64decode(msg.get("data", "")))
                continue
            if t not in ("transcript.user.delta",):
                print("agent event        :", t, {k: v for k, v in msg.items()
                                                  if k in ("text", "name", "arguments", "status", "code", "message")})
            if t == "reply.done" and not sent_audio:
                sent_audio = True
                step = RATE // 20 * 2
                for i in range(0, len(audio), step):
                    await ws.send(json.dumps({"type": "input.audio", "audio": base64.b64encode(audio[i:i + step]).decode()}))
                    await asyncio.sleep(0.05)
                for _ in range(40):  # two seconds of silence
                    await ws.send(json.dumps({"type": "input.audio", "audio": base64.b64encode(b"\x00" * step).decode()}))
                    await asyncio.sleep(0.05)
            if t == "tool.call":
                pending.append({"call_id": msg["call_id"], "result": {"sounds_prepared": False}})
            if t in ("reply.started", "input.speech.started", "reply.done"):
                last = t
            if last == "reply.done" and pending:
                for p in pending:
                    await ws.send(json.dumps({"type": "tool.result", "call_id": p["call_id"], "result": json.dumps(p["result"])}))
                pending.clear()
            if t == "transcript.agent" and sent_audio and "follow" not in (msg.get("text") or "").lower() and time.monotonic() - started > 8:
                print("agent follow-up    :", msg.get("text"))
            if time.monotonic() - started > 45 or t in ("session.error", "session.ended"):
                break
        print("agent audio bytes  :", audio_bytes)
        await ws.send(json.dumps({"type": "session.end"}))


async def main() -> None:
    if not KEY:
        sys.exit("ASSEMBLYAI_API_KEY is not set in .env")
    make_clip()
    audio = pcm()
    for name, check, limit in (("tokens", check_tokens(), 30), ("stt", check_stt(audio), 60), ("agent", check_agent(audio), 70)):
        try:
            await asyncio.wait_for(check, limit)
        except asyncio.TimeoutError:
            print(f"{name}: no end after {limit} s")
        except Exception as error:  # a failing check must not hide the next one
            print(f"{name}: {type(error).__name__}: {error}")


if __name__ == "__main__":
    asyncio.run(main())
