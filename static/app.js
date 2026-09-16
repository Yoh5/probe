// Probe - the candidate's side.
//
// Two AssemblyAI connections, one microphone:
//
//   mic ──┬── Voice Agent API   : the conversation. It hears, decides what to
//         │                       say, speaks, and calls our tool.
//         └── Realtime STT      : the same audio again, for the timing of every
//                                 word. The agent connection returns text only,
//                                 and the verdict rests on timings.
//
// When the agent calls `assess_answer`, this page collects the words of the
// answer that just ended and asks the server for the verdict. The server
// decides; the agent only chooses how to word the next question.
//
// WHAT THE CANDIDATE SEES: the conversation, and nothing else. No score, no
// signal, no hint that an answer was probed. The interviewer's instructions live
// in a stored agent at AssemblyAI, not in this file, so they cannot be read from
// the page either.

const AGENT_URL = "wss://agents.assemblyai.com/v1/ws";
const STT_URL = "wss://streaming.assemblyai.com/v3/ws";
const RATE = 24000;
// How long to wait for the transcription connection to finish the last words of
// an answer before assessing it. The agent holds its turn meanwhile.
const WORDS_SETTLE_MS = 1200;

const COPY = {
  en: { title: "A conversation, not a form.", lede: "Five minutes, out loud. The interviewer listens, answers, and asks what comes next from what you say.",
        terms1: "<b>Your voice is transcribed as you speak</b> by AssemblyAI. The audio itself is not kept.",
        terms2: "The transcript is kept and used to prepare a report for the recruiter. It suggests what to ask next; it never decides anything on its own.",
        start: "I agree, start the interview", hint: "Headphones keep the interviewer's voice out of your microphone.",
        listening: "Listening", speaking: "The interviewer is speaking", connecting: "Connecting", you: "You", them: "Interviewer",
        finish: "End the interview", saving: "Saving the interview", savingLede: "A few seconds. Keep this page open.",
        done: "Thank you. That's everything.", doneLede: "The recruiter has your interview and will be in touch.", retry: "Try again" },
  fr: { title: "Une conversation, pas un formulaire.", lede: "Cinq minutes, à voix haute. L'entretien écoute, répond, et enchaîne à partir de ce que vous dites.",
        terms1: "<b>Votre voix est transcrite au fil de la parole</b> par AssemblyAI. L'audio n'est pas conservé.",
        terms2: "La transcription est conservée et sert à préparer un compte rendu pour le recruteur. Elle suggère quoi demander ensuite ; elle ne décide jamais rien seule.",
        start: "J'accepte, commencer l'entretien", hint: "Un casque évite que la voix de l'entretien entre dans votre micro.",
        listening: "À vous", speaking: "L'entretien parle", connecting: "Connexion", you: "Vous", them: "Entretien",
        finish: "Terminer l'entretien", saving: "Enregistrement de l'entretien", savingLede: "Quelques secondes. Gardez cette page ouverte.",
        done: "Merci, c'est terminé.", doneLede: "Le recruteur a votre entretien et vous recontactera.", retry: "Réessayer" },
  es: { title: "Una conversación, no un formulario.", lede: "Cinco minutos, en voz alta. La entrevista escucha, responde y sigue con lo que usted dice.",
        terms1: "<b>Su voz se transcribe mientras habla</b> con AssemblyAI. El audio no se conserva.",
        terms2: "La transcripción se conserva y sirve para preparar un informe para el reclutador. Sugiere qué preguntar después; nunca decide nada por sí sola.",
        start: "Acepto, empezar la entrevista", hint: "Los auriculares evitan que la voz de la entrevista entre en su micrófono.",
        listening: "Le escucho", speaking: "La entrevista habla", connecting: "Conectando", you: "Usted", them: "Entrevista",
        finish: "Terminar la entrevista", saving: "Guardando la entrevista", savingLede: "Unos segundos. Mantenga esta página abierta.",
        done: "Gracias, eso es todo.", doneLede: "El reclutador tiene su entrevista y se pondrá en contacto.", retry: "Reintentar" },
  de: { title: "Ein Gespräch, kein Formular.", lede: "Fünf Minuten, laut gesprochen. Das Gespräch hört zu, antwortet und knüpft an Ihre Worte an.",
        terms1: "<b>Ihre Stimme wird beim Sprechen transkribiert</b> von AssemblyAI. Das Audio wird nicht gespeichert.",
        terms2: "Das Transkript wird gespeichert und dient einem Bericht für die Recruiterin oder den Recruiter. Es schlägt vor, was als Nächstes zu fragen ist; es entscheidet nie allein.",
        start: "Einverstanden, Gespräch starten", hint: "Kopfhörer halten die Stimme des Gesprächs aus Ihrem Mikrofon.",
        listening: "Sie sind dran", speaking: "Das Gespräch spricht", connecting: "Verbindung", you: "Sie", them: "Gespräch",
        finish: "Gespräch beenden", saving: "Gespräch wird gespeichert", savingLede: "Ein paar Sekunden. Lassen Sie die Seite offen.",
        done: "Danke, das war alles.", doneLede: "Das Gespräch liegt vor und man meldet sich bei Ihnen.", retry: "Erneut versuchen" },
  it: { title: "Una conversazione, non un modulo.", lede: "Cinque minuti, ad alta voce. Il colloquio ascolta, risponde e prosegue da ciò che dice.",
        terms1: "<b>La sua voce viene trascritta mentre parla</b> da AssemblyAI. L'audio non viene conservato.",
        terms2: "La trascrizione viene conservata e serve a preparare un resoconto per il selezionatore. Suggerisce cosa chiedere dopo; non decide mai nulla da sola.",
        start: "Accetto, iniziare il colloquio", hint: "Le cuffie tengono la voce del colloquio fuori dal microfono.",
        listening: "A lei", speaking: "Il colloquio parla", connecting: "Connessione", you: "Lei", them: "Colloquio",
        finish: "Terminare il colloquio", saving: "Salvataggio del colloquio", savingLede: "Pochi secondi. Tenga aperta la pagina.",
        done: "Grazie, è tutto.", doneLede: "Il selezionatore ha il colloquio e la ricontatterà.", retry: "Riprovare" },
  pt: { title: "Uma conversa, não um formulário.", lede: "Cinco minutos, em voz alta. A entrevista ouve, responde e continua a partir do que você diz.",
        terms1: "<b>A sua voz é transcrita enquanto fala</b> pela AssemblyAI. O áudio não é guardado.",
        terms2: "A transcrição é guardada e serve para preparar um relatório para o recrutador. Sugere o que perguntar a seguir; nunca decide nada sozinha.",
        start: "Aceito, começar a entrevista", hint: "Auscultadores evitam que a voz da entrevista entre no seu microfone.",
        listening: "É consigo", speaking: "A entrevista fala", connecting: "A ligar", you: "Você", them: "Entrevista",
        finish: "Terminar a entrevista", saving: "A guardar a entrevista", savingLede: "Alguns segundos. Mantenha esta página aberta.",
        done: "Obrigado, é tudo.", doneLede: "O recrutador tem a sua entrevista e entrará em contacto.", retry: "Tentar de novo" },
};

let languages = [];
let language = "en";
let agentWs, sttWs, audioContext, playerContext, player, stream;
let samplesSent = 0;
let words = [];            // every final word from the transcription connection
let lastWordAt = 0;
let answerStartMs = 0;     // audio clock at the end of the agent's last reply
let baselineWords = null;  // the warm-up answer: what later answers are compared to
let turns = [];
let assessments = [];
let pendingResults = [];
let lastEvent = null;
let finished = false;
let failed = false;

const clockMs = () => (samplesSent / RATE) * 1000;
const $ = (id) => document.getElementById(id);
const copy = () => COPY[language] || COPY.en;

function show(name) {
  for (const screen of document.querySelectorAll(".screen")) screen.hidden = screen.id !== `screen-${name}`;
}

// -- the line ---------------------------------------------------------------------
//
// One canvas, two states. The candidate's voice draws mint bars from the real
// microphone level; while the interviewer speaks, an amber wave travels across.
// Nothing else on the page animates.

const levels = new Array(96).fill(0);
let speaking = false;
let phase = 0;
const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function drawLine(canvas) {
  if (!canvas) return;
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const context = canvas.getContext("2d");
  context.scale(ratio, ratio);
  context.clearRect(0, 0, width, height);
  const middle = height / 2;
  const step = width / levels.length;

  context.lineWidth = 2;
  context.lineCap = "round";
  context.strokeStyle = speaking ? "#E9B44C" : "#74D3AE";
  for (let i = 0; i < levels.length; i++) {
    const x = i * step + step / 2;
    // Idle, the line breathes so the page looks live before anyone speaks;
    // while the interviewer talks, an amber wave travels across it.
    const idle = still ? 0.05 : 0.05 + Math.abs(Math.sin(i * 0.12 + phase * 0.35)) * 0.06;
    const travelling = speaking
      ? Math.abs(Math.sin(i * 0.22 + phase)) * (still ? 0.25 : 0.55)
      : Math.max(levels[i], idle);
    const size = Math.max(1.2, travelling * (height * 0.44));
    context.beginPath();
    context.moveTo(x, middle - size);
    context.lineTo(x, middle + size);
    context.stroke();
  }
  context.strokeStyle = "rgba(242,239,230,.18)";
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(0, middle);
  context.lineTo(width, middle);
  context.stroke();
}

function animate() {
  if (!still) phase += speaking ? 0.14 : 0.03;
  drawLine($("line-welcome")?.offsetParent ? $("line-welcome") : $("line-live"));
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);

function pushLevel(peak) {
  levels.push(Math.min(1, peak * 2.2));
  levels.shift();
}

// -- language and copy ----------------------------------------------------------------

function applyCopy() {
  const text = copy();
  document.documentElement.lang = language;
  $("t-title").textContent = text.title;
  $("t-lede").textContent = text.lede;
  $("t-terms-1").innerHTML = text.terms1;   // one bolded clause, written above, no user input
  $("t-terms-2").textContent = text.terms2;
  $("t-start").textContent = text.start;
  $("t-hint").textContent = text.hint;
  $("finish").textContent = text.finish;
  $("t-saving").textContent = text.saving;
  $("t-saving-lede").textContent = text.savingLede;
  $("t-done").textContent = text.done;
  $("t-done-lede").textContent = text.doneLede;
  $("retry").textContent = text.retry;
  $("state-label").textContent = text.connecting;
}

function renderLanguages() {
  const nav = $("languages");
  nav.replaceChildren();
  for (const offered of languages) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = offered.name;
    button.setAttribute("aria-pressed", String(offered.code === language));
    button.addEventListener("click", () => {
      language = offered.code;
      applyCopy();
      renderLanguages();
    });
    nav.append(button);
  }
}

async function loadInterview() {
  try {
    const response = await fetch("/api/interview");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const brief = await response.json();
    languages = brief.languages;
    const preferred = (navigator.language || "en").slice(0, 2);
    language = languages.some((l) => l.code === preferred) ? preferred : languages[0].code;
  } catch (error) {
    return fail("The interview could not load", "The server did not answer.",
      `Reason: ${error.message}. Reload the page in a moment.`);
  }
  renderLanguages();
  applyCopy();
  $("start").disabled = false;
}

// -- starting -------------------------------------------------------------------------

async function start() {
  $("start").disabled = true;
  $("start").prepend(Object.assign(document.createElement("span"), { className: "spinner" }));

  let session;
  try {
    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    session = body;
  } catch (error) {
    return fail("The interview could not start", "The service that hears and answers you did not respond.",
      `Reason: ${error.message}. Try again in a moment; if it keeps happening, tell the recruiter.`);
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (error) {
    if (error.name === "NotAllowedError") {
      return fail("Microphone access is blocked", "The interview needs your microphone, and the browser refused it.",
        "Click the icon at the left of the address bar, set Microphone to Allow, then press Try again.");
    }
    return fail("No microphone found", "The browser could not open a microphone.",
      `Plug in or enable a microphone, then press Try again. (${error.name})`);
  }

  openAgent(session);
  openTranscription(session.streaming);
}

function openAgent(session) {
  agentWs = new WebSocket(`${AGENT_URL}?token=${encodeURIComponent(session.agent)}`);
  // The agent is stored at AssemblyAI: the browser sends its id, not its instructions.
  agentWs.onopen = () => agentWs.send(JSON.stringify({ type: "session.update", session: { agent_id: session.agent_id } }));
  agentWs.onmessage = (event) => handleAgent(JSON.parse(event.data));
  agentWs.onclose = (event) => {
    if (!finished && !failed && event.code !== 1000) {
      fail("The connection was lost", "The interview stopped before it was finished, and it was not saved.",
        "Check your internet connection, then press Try again to start over.");
    }
  };
}

function openTranscription(token) {
  const url = new URL(STT_URL);
  url.searchParams.set("token", token);
  url.searchParams.set("speech_model", "universal-3-5-pro");
  url.searchParams.set("sample_rate", String(RATE));
  url.searchParams.set("encoding", "pcm_s16le");
  url.searchParams.set("format_turns", "true");
  sttWs = new WebSocket(url);
  sttWs.onmessage = (event) => {
    const message = JSON.parse(event.data);
    // Only finalised turns carry settled timings; partials would be counted twice.
    if (message.type === "Turn" && message.end_of_turn) {
      for (const word of message.words || []) words.push(word);
      lastWordAt = performance.now();
    }
  };
}

// -- audio -----------------------------------------------------------------------------

async function startAudio() {
  audioContext = new AudioContext({ sampleRate: RATE });
  await audioContext.audioWorklet.addModule("/static/pcm-worklet.js");
  playerContext = new AudioContext({ sampleRate: RATE });
  await playerContext.audioWorklet.addModule("/static/player-worklet.js");
  player = new AudioWorkletNode(playerContext, "agent-player");
  player.connect(playerContext.destination);
  player.port.onmessage = ({ data }) => setSpeaking(Boolean(data));

  const source = audioContext.createMediaStreamSource(stream);
  const chunker = new AudioWorkletNode(audioContext, "pcm-chunker");
  chunker.port.onmessage = ({ data }) => {
    const pcm = new Int16Array(data.length);
    let peak = 0;
    for (let i = 0; i < data.length; i++) {
      const sample = Math.max(-1, Math.min(1, data[i]));
      pcm[i] = sample * 0x7fff;
      peak = Math.max(peak, Math.abs(sample));
    }
    samplesSent += data.length;
    pushLevel(peak);
    const bytes = new Uint8Array(pcm.buffer);
    if (agentWs?.readyState === WebSocket.OPEN) {
      agentWs.send(JSON.stringify({ type: "input.audio", audio: base64(bytes) }));
    }
    if (sttWs?.readyState === WebSocket.OPEN) sttWs.send(bytes);
  };
  source.connect(chunker);
}

function base64(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function playAgentAudio(base64Audio) {
  const binary = atob(base64Audio);
  const pcm = new Int16Array(binary.length / 2);
  for (let i = 0; i < pcm.length; i++) {
    pcm[i] = (binary.charCodeAt(i * 2 + 1) << 8) | binary.charCodeAt(i * 2);
  }
  const floats = new Float32Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) floats[i] = pcm[i] / 0x8000;
  player?.port.postMessage(floats);
}

function setSpeaking(on) {
  speaking = on;
  $("dot").classList.toggle("speaking", on);
  $("state-label").textContent = on ? copy().speaking : copy().listening;
}

// -- the agent's events -------------------------------------------------------------------

function handleAgent(message) {
  switch (message.type) {
    case "session.ready":
      // The stored agent has no fixed greeting: a recorded one could not be
      // translated. It opens the interview itself, in the chosen language.
      startAudio().then(() => {
        show("interview");
        agentWs.send(JSON.stringify({ type: "reply.create",
          instructions: "Open the interview now: greet in one short sentence, then ask the warm-up question." }));
      });
      break;
    case "reply.audio":
      playAgentAudio(message.data);
      break;
    case "transcript.agent":
      addTurn("them", message.text);
      break;
    case "transcript.user":
      addTurn("you", message.text);
      break;
    case "input.speech.started":
      player?.port.postMessage("flush");   // barge-in: stop the half-spoken sentence
      lastEvent = "input.speech.started";
      break;
    case "reply.started":
      lastEvent = "reply.started";
      break;
    case "reply.done":
      lastEvent = "reply.done";
      // The interviewer has stopped: whatever is said from now on is the answer.
      answerStartMs = clockMs();
      if (message.status === "interrupted") pendingResults = [];
      else flushResults();
      break;
    case "tool.call":
      handleTool(message);
      break;
    case "session.error":
      fail("The interview stopped", "The voice service reported a problem.",
        `${message.code || ""} ${message.message || ""}`.trim() + " Press Try again to start over.");
      break;
    default:
      break;
  }
}

async function handleTool(call) {
  if (call.name === "end_interview") {
    queueResult(call.call_id, { ok: true });
    return finish();
  }
  if (call.name !== "assess_answer") return queueResult(call.call_id, { error: "unknown tool" });

  const topic = String(call.arguments?.topic_id ?? "warmup");
  const warmup = !baselineWords;
  const start = answerStartMs;
  await settle();
  const answerWords = words.filter((w) => w.start >= start);

  let verdict;
  try {
    const response = await fetch("/api/assess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer_words: answerWords, baseline_words: warmup ? null : baselineWords }),
    });
    verdict = await response.json();
    if (!response.ok) throw new Error(verdict.detail || `HTTP ${response.status}`);
  } catch (error) {
    // A failed assessment must not derail the interview: the agent carries on.
    verdict = { verdict: "not_measured", instruction: "Ask your next question.", error: error.message };
  }
  if (warmup && answerWords.length) baselineWords = answerWords;
  assessments.push({ topic_id: topic, claim: call.arguments?.claim ?? "", words: answerWords, ...verdict });
  queueResult(call.call_id, { instruction: verdict.instruction, verdict: verdict.verdict });
}

// Give the transcription connection a moment to finalise the last words of the
// answer: it settles a beat after the agent's own turn detection fires.
function settle() {
  return new Promise((resolve) => {
    const deadline = performance.now() + WORDS_SETTLE_MS;
    const tick = () => {
      if (performance.now() - lastWordAt > 400 || performance.now() > deadline) resolve();
      else setTimeout(tick, 100);
    };
    tick();
  });
}

function queueResult(callId, result) {
  pendingResults.push({ call_id: callId, result });
  flushResults();
}

function flushResults() {
  if (lastEvent !== "reply.done" || !pendingResults.length || agentWs?.readyState !== WebSocket.OPEN) return;
  for (const pending of pendingResults) {
    agentWs.send(JSON.stringify({ type: "tool.result", call_id: pending.call_id, result: JSON.stringify(pending.result) }));
  }
  pendingResults = [];
}

// -- the conversation on screen ------------------------------------------------------------

function addTurn(role, text) {
  if (!text) return;
  turns.push({ role: role === "you" ? "candidate" : "interviewer", text, at: Math.round(clockMs()) });
  if (role === "them") $("said").textContent = text;   // the question stays large while it is answered
  const line = document.createElement("p");
  line.className = `turn ${role}`;
  line.append(Object.assign(document.createElement("span"), { textContent: role === "you" ? copy().you : copy().them }), text);
  $("transcript").prepend(line);   // newest first: the column is reversed
}

// -- the end ---------------------------------------------------------------------------------

async function finish() {
  if (finished) return;
  finished = true;
  show("saving");
  stream?.getTracks().forEach((track) => track.stop());
  setTimeout(() => agentWs?.readyState === WebSocket.OPEN && agentWs.send(JSON.stringify({ type: "session.end" })), 200);
  if (sttWs?.readyState === WebSocket.OPEN) sttWs.send(JSON.stringify({ type: "Terminate" }));

  try {
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recordedAt: new Date().toISOString(), language, turns, assessments, words }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    $("report-link").href = `/report?id=${encodeURIComponent(body.id)}`;
    show("done");
  } catch (error) {
    fail("Your interview was not saved", "The conversation finished, but saving it failed.",
      `Reason: ${error.message}. Keep this page open and tell the recruiter.`, false);
  }
}

function fail(title, text, fix, canRetry = true) {
  failed = true;
  $("error-title").textContent = title;
  $("error-text").textContent = text;
  $("error-fix").textContent = fix;
  $("retry").hidden = !canRetry;
  show("error");
  stream?.getTracks().forEach((track) => track.stop());
  for (const socket of [agentWs, sttWs]) {
    if (socket?.readyState === WebSocket.OPEN) socket.close(1000);
  }
}

$("start").addEventListener("click", start);
$("finish").addEventListener("click", finish);
$("retry").addEventListener("click", () => location.reload());
loadInterview();
