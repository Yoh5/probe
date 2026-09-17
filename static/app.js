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
const WORDS_SETTLE_MS = 700;
// How long the interviewer leaves a candidate who has spoken and then stopped
// before taking the turn back. Nothing is armed until they have spoken: someone
// who has not started yet is thinking, and has a visible clock of their own.
const AFTER_SPEAKING_MS = 5000;
// Before that, the page says out loud that thinking is allowed.
const PATIENCE_MS = 2000;
// How long the candidate has for one answer, and when the clock starts to press.
// A spoken answer that runs past ninety seconds has stopped being an answer.
const ANSWER_MS = 90000;
const URGENT_MS = 15000;
// The agent is blocked until it has its tool result. Sending it once the reply
// is done is the polite order; waiting for that forever is a hang.
const RESULT_GRACE_MS = 900;
// After the last question, how long the interviewer gets to thank the candidate
// and end the interview itself before the page ends it for them.
const LAST_WORD_MS = 25000;

const COPY = {
  en: { title: "A conversation, not a form.", lede: "Five minutes, out loud. The interviewer listens, answers, and asks what comes next from what you say.",
        terms1: "Your voice is transcribed as you speak", terms1b: "By AssemblyAI. The audio itself is not kept.",
        terms2: "The transcript goes to the recruiter", terms2b: "It suggests what to ask next; it never decides anything on its own.",
        terms3: "Ninety seconds for each answer", terms3b: "The countdown is on screen. Take all of it if you need it.",
        start: "I agree, start the interview", hint: "Headphones keep the interviewer's voice out of your microphone.",
        listening: "Listening", thinking: "Take your time", speaking: "The interviewer is speaking", connecting: "Connecting", you: "You", them: "Interviewer",
        finish: "End the interview", budget: "to answer", stage: "Part {n} of {total}", saving: "Saving the interview", savingLede: "A few seconds. Keep this page open.",
        done: "Thank you. That's everything.", doneLede: "The recruiter has your interview and will be in touch.", retry: "Try again",
        spentTitle: "This interview has already been taken", spentText: "Each link works once, so the questions cannot be heard twice.", spentFix: "If you think this is a mistake, reply to the email that sent you here.",
        goneTitle: "This link is not valid", goneText: "It may have been mistyped, or withdrawn.", goneFix: "Reply to the email that sent you here and ask for a new one." },
  fr: { title: "Une conversation, pas un formulaire.", lede: "Cinq minutes, à voix haute. L'entretien écoute, répond, et enchaîne à partir de ce que vous dites.",
        terms1: "Votre voix est transcrite au fil de la parole", terms1b: "Par AssemblyAI. L'audio n'est pas conservé.",
        terms2: "La transcription est remise au recruteur", terms2b: "Elle suggère quoi demander ensuite ; elle ne décide jamais rien seule.",
        terms3: "Quatre-vingt-dix secondes par réponse", terms3b: "Le compte à rebours est à l'écran. Prenez-les toutes s'il le faut.",
        start: "J'accepte, commencer l'entretien", hint: "Un casque évite que la voix de l'entretien entre dans votre micro.",
        listening: "À vous", thinking: "Prenez votre temps", speaking: "L'entretien parle", connecting: "Connexion", you: "Vous", them: "Entretien",
        finish: "Terminer l'entretien", budget: "pour répondre", stage: "Partie {n} sur {total}", saving: "Enregistrement de l'entretien", savingLede: "Quelques secondes. Gardez cette page ouverte.",
        done: "Merci, c'est terminé.", doneLede: "Le recruteur a votre entretien et vous recontactera.", retry: "Réessayer",
        spentTitle: "Cet entretien a déjà été passé", spentText: "Chaque lien ne sert qu'une fois, pour que les questions ne soient pas entendues deux fois.", spentFix: "Si vous pensez qu'il s'agit d'une erreur, répondez au message qui vous a envoyé ici.",
        goneTitle: "Ce lien n'est pas valide", goneText: "Il a peut-être été mal recopié, ou retiré.", goneFix: "Répondez au message qui vous a envoyé ici pour en demander un nouveau." },
  es: { title: "Una conversación, no un formulario.", lede: "Cinco minutos, en voz alta. La entrevista escucha, responde y sigue con lo que usted dice.",
        terms1: "Su voz se transcribe mientras habla", terms1b: "Con AssemblyAI. El audio no se conserva.",
        terms2: "La transcripción se entrega al reclutador", terms2b: "Sugiere qué preguntar después; nunca decide nada por sí sola.",
        terms3: "Noventa segundos por respuesta", terms3b: "La cuenta atrás está en pantalla. Tómelos todos si hace falta.",
        start: "Acepto, empezar la entrevista", hint: "Los auriculares evitan que la voz de la entrevista entre en su micrófono.",
        listening: "Le escucho", thinking: "Tómese su tiempo", speaking: "La entrevista habla", connecting: "Conectando", you: "Usted", them: "Entrevista",
        finish: "Terminar la entrevista", budget: "para responder", stage: "Parte {n} de {total}", saving: "Guardando la entrevista", savingLede: "Unos segundos. Mantenga esta página abierta.",
        done: "Gracias, eso es todo.", doneLede: "El reclutador tiene su entrevista y se pondrá en contacto.", retry: "Reintentar",
        spentTitle: "Esta entrevista ya se ha realizado", spentText: "Cada enlace sirve una sola vez, para que las preguntas no se oigan dos veces.", spentFix: "Si cree que es un error, responda al mensaje que le trajo aquí.",
        goneTitle: "Este enlace no es válido", goneText: "Puede estar mal copiado, o haber sido retirado.", goneFix: "Responda al mensaje que le trajo aquí y pida uno nuevo." },
  de: { title: "Ein Gespräch, kein Formular.", lede: "Fünf Minuten, laut gesprochen. Das Gespräch hört zu, antwortet und knüpft an Ihre Worte an.",
        terms1: "Ihre Stimme wird beim Sprechen transkribiert", terms1b: "Von AssemblyAI. Das Audio wird nicht gespeichert.",
        terms2: "Das Transkript geht an die Recruiterin oder den Recruiter", terms2b: "Es schlägt vor, was als Nächstes zu fragen ist; es entscheidet nie allein.",
        terms3: "Neunzig Sekunden pro Antwort", terms3b: "Der Countdown steht auf dem Bildschirm. Nehmen Sie sich die Zeit.",
        start: "Einverstanden, Gespräch starten", hint: "Kopfhörer halten die Stimme des Gesprächs aus Ihrem Mikrofon.",
        listening: "Sie sind dran", thinking: "Lassen Sie sich Zeit", speaking: "Das Gespräch spricht", connecting: "Verbindung", you: "Sie", them: "Gespräch",
        finish: "Gespräch beenden", budget: "zum Antworten", stage: "Teil {n} von {total}", saving: "Gespräch wird gespeichert", savingLede: "Ein paar Sekunden. Lassen Sie die Seite offen.",
        done: "Danke, das war alles.", doneLede: "Das Gespräch liegt vor und man meldet sich bei Ihnen.", retry: "Erneut versuchen",
        spentTitle: "Dieses Gespräch wurde bereits geführt", spentText: "Jeder Link gilt einmal, damit die Fragen nicht zweimal zu hören sind.", spentFix: "Wenn das ein Irrtum ist, antworten Sie auf die Nachricht, die Sie hergeschickt hat.",
        goneTitle: "Dieser Link ist ungültig", goneText: "Vielleicht vertippt, vielleicht zurückgezogen.", goneFix: "Antworten Sie auf die Nachricht, die Sie hergeschickt hat, und bitten Sie um einen neuen." },
  it: { title: "Una conversazione, non un modulo.", lede: "Cinque minuti, ad alta voce. Il colloquio ascolta, risponde e prosegue da ciò che dice.",
        terms1: "La sua voce viene trascritta mentre parla", terms1b: "Da AssemblyAI. L'audio non viene conservato.",
        terms2: "La trascrizione va al selezionatore", terms2b: "Suggerisce cosa chiedere dopo; non decide mai nulla da sola.",
        terms3: "Novanta secondi per ogni risposta", terms3b: "Il conto alla rovescia è sullo schermo. Li prenda tutti se serve.",
        start: "Accetto, iniziare il colloquio", hint: "Le cuffie tengono la voce del colloquio fuori dal microfono.",
        listening: "A lei", thinking: "Con calma", speaking: "Il colloquio parla", connecting: "Connessione", you: "Lei", them: "Colloquio",
        finish: "Terminare il colloquio", budget: "per rispondere", stage: "Parte {n} di {total}", saving: "Salvataggio del colloquio", savingLede: "Pochi secondi. Tenga aperta la pagina.",
        done: "Grazie, è tutto.", doneLede: "Il selezionatore ha il colloquio e la ricontatterà.", retry: "Riprovare",
        spentTitle: "Questo colloquio è già stato sostenuto", spentText: "Ogni link vale una volta sola, perché le domande non si sentano due volte.", spentFix: "Se pensa sia un errore, risponda al messaggio che l'ha portata qui.",
        goneTitle: "Questo link non è valido", goneText: "Potrebbe essere stato copiato male, o ritirato.", goneFix: "Risponda al messaggio che l'ha portata qui e ne chieda uno nuovo." },
  pt: { title: "Uma conversa, não um formulário.", lede: "Cinco minutos, em voz alta. A entrevista ouve, responde e continua a partir do que você diz.",
        terms1: "A sua voz é transcrita enquanto fala", terms1b: "Pela AssemblyAI. O áudio não é guardado.",
        terms2: "A transcrição vai para o recrutador", terms2b: "Sugere o que perguntar a seguir; nunca decide nada sozinha.",
        terms3: "Noventa segundos para cada resposta", terms3b: "A contagem está no ecrã. Use-a toda se precisar.",
        start: "Aceito, começar a entrevista", hint: "Auscultadores evitam que a voz da entrevista entre no seu microfone.",
        listening: "É consigo", thinking: "Não tenha pressa", speaking: "A entrevista fala", connecting: "A ligar", you: "Você", them: "Entrevista",
        finish: "Terminar a entrevista", budget: "para responder", stage: "Parte {n} de {total}", saving: "A guardar a entrevista", savingLede: "Alguns segundos. Mantenha esta página aberta.",
        done: "Obrigado, é tudo.", doneLede: "O recrutador tem a sua entrevista e entrará em contacto.", retry: "Tentar de novo",
        spentTitle: "Esta entrevista já foi realizada", spentText: "Cada ligação serve uma vez, para que as perguntas não sejam ouvidas duas vezes.", spentFix: "Se acha que é um engano, responda à mensagem que o trouxe aqui.",
        goneTitle: "Esta ligação não é válida", goneText: "Pode ter sido mal copiada, ou retirada.", goneFix: "Responda à mensagem que o trouxe aqui e peça uma nova." },
};

let languages = [];
let parts = 0;             // how many parts the interview has, warm-up included
let role = "";
// The candidate's own link is /i/<id>. An interview reached any other way is a
// rehearsal, and is allowed: it is the recruiter trying their own interview.
const invite = (location.pathname.match(/^[/]i[/]([0-9a-f]{32})$/) || [])[1] || null;
let language = "en";
let agentWs, sttWs, audioContext, playerContext, player, stream;
let samplesSent = 0;
let words = [];            // every final word from the transcription connection
let lastWordAt = 0;
let answerStartMs = 0;     // audio clock at the end of the agent's last reply
let baselineWords = null;  // the warm-up, once it is long enough to compare against
let warmupWords = [];      // what has been said in the warm-up so far, while it is still short
let turns = [];
let assessments = [];
let pendingResults = [];
let flushTimer = null;
let assessing = null;      // the assessment of the current answer, already under way
const seen = new Set();    // topic ids the interview has reached, for the progress mark
const answered = new Set();   // the start of every answer counted against the question limit
let lastCallTimer = null;
let turnId = 0;            // which answer is being given: the identity of an assessment
let lastEvent = null;
let agentSpoke = false;   // did the last reply actually say anything out loud?
let finished = false;
let failed = false;

const clockMs = () => (samplesSent / RATE) * 1000;
const $ = (id) => document.getElementById(id);
const copy = () => COPY[language] || COPY.en;

function show(name) {
  for (const screen of document.querySelectorAll(".screen")) screen.hidden = screen.id !== `screen-${name}`;
}

// -- the microphone ---------------------------------------------------------------
//
// One number on screen, and it is the real one: the level of the audio actually
// being sent. The ring grows with it, so a candidate can see the microphone is
// hearing them without being asked to read anything.

let speaking = false;
let level = 0;
let levelPainted = 0;

function pushLevel(peak) {
  // Rises with the voice, falls back slowly, so the ring follows speech rather
  // than flickering on every 50 ms packet.
  level = Math.max(Math.min(1, peak * 2.4), level * 0.82);
  const rounded = Math.round(level * 20) / 20;
  if (rounded === levelPainted) return;      // the same value is not worth a repaint
  levelPainted = rounded;
  $("mic")?.style.setProperty("--level", String(rounded));
}

// -- language and copy ----------------------------------------------------------------

function applyCopy() {
  const text = copy();
  document.documentElement.lang = language;
  $("t-title").textContent = text.title;
  $("t-lede").textContent = text.lede;
  for (const n of [1, 2, 3]) {
    $(`t-terms-${n}`).textContent = text[`terms${n}`];
    $(`t-terms-${n}b`).textContent = text[`terms${n}b`];
  }
  $("t-start").textContent = text.start;
  $("t-hint").textContent = text.hint;
  $("finish").textContent = text.finish;
  $("t-saving").textContent = text.saving;
  $("t-saving-lede").textContent = text.savingLede;
  $("t-done").textContent = text.done;
  $("t-done-lede").textContent = text.doneLede;
  $("retry").textContent = text.retry;
  $("clock-label").textContent = text.budget;
  $("role").textContent = role;
  $("state-label").textContent = text.connecting;
  renderStage();
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
    parts = brief.parts || 0;
    role = brief.role || "";
    const preferred = (navigator.language || "en").slice(0, 2);
    language = languages.some((l) => l.code === preferred) ? preferred : languages[0].code;
  } catch (error) {
    return fail("The interview could not load", "The server did not answer.",
      `Reason: ${error.message}. Reload the page in a moment.`);
  }
  renderLanguages();
  applyCopy();
  if (invite && !(await linkIsLive())) return;
  $("start").disabled = false;
}

// Reading the link does not spend it; this only asks whether it is still good, so
// a candidate who opens it, reads the page and comes back later still has their
// interview.
async function linkIsLive() {
  try {
    const response = await fetch(`/api/invites/${invite}`);
    if (response.ok) {
      const state = await response.json();
      if (state.status !== "done") return true;
      fail(copy().spentTitle, copy().spentText, copy().spentFix);
      return false;
    }
    if (response.status === 404) {
      fail(copy().goneTitle, copy().goneText, copy().goneFix);
      return false;
    }
  } catch (error) {
    // The link could not be checked. Letting them through is the kinder mistake:
    // the server refuses a spent invitation again when the interview starts.
    return true;
  }
  return true;
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
      body: JSON.stringify({ language, invite }),
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
    if (message.type === "Turn" && message.end_of_turn) sttHeard(message.words);
  };
}

function sttHeard(heard) {
  for (const word of heard || []) words.push(word);
  lastWordAt = performance.now();
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
  for (let i = 0; i < bytes.length; i += 8192) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
  }
  return btoa(binary);
}

function playAgentAudio(base64Audio) {
  const binary = atob(base64Audio);
  const floats = new Float32Array(binary.length / 2);
  for (let i = 0; i < floats.length; i++) {
    const sample = (binary.charCodeAt(i * 2 + 1) << 8) | binary.charCodeAt(i * 2);
    floats[i] = (sample >= 0x8000 ? sample - 0x10000 : sample) / 0x8000;
  }
  player?.port.postMessage(floats);
}

// -- whose turn it is -------------------------------------------------------------
//
// Two clocks, and neither of them hurries anyone.
//
// The budget is shown. A candidate who has not started talking is not silent,
// they are thinking, and they can see exactly how long they have - so nothing
// interrupts them and nothing asks whether they are still there. That was the
// wrong thing to build: it prompted people who were simply working out what to
// say.
//
// The other clock only ever starts AFTER the candidate has spoken and stopped.
// Five seconds of that, and the turn goes back to the interviewer, either to
// follow up or to move on. AssemblyAI waits the same five seconds on its own; this
// is here for when its turn detection does not fire at all, which would otherwise
// leave two parties both waiting to be spoken to.

let patienceTimer = null;
let budgetTimer = null;
let afterSpeaking = null;
let clockTicker = null;
let budgetEndsAt = 0;

function holdFloor() {
  clearTimeout(patienceTimer);
  clearTimeout(budgetTimer);
  clearTimeout(afterSpeaking);
  clearInterval(clockTicker);
  patienceTimer = budgetTimer = afterSpeaking = clockTicker = null;
  $("clock")?.setAttribute("hidden", "");
}

function giveTheFloor() {
  holdFloor();
  turnId += 1;
  budgetEndsAt = performance.now() + ANSWER_MS;
  $("clock")?.removeAttribute("hidden");
  renderClock();
  clockTicker = setInterval(renderClock, 500);
  patienceTimer = setTimeout(() => {
    if (!speaking) $("state-label").textContent = copy().thinking;
  }, PATIENCE_MS);
  budgetTimer = setTimeout(timeIsUp, ANSWER_MS);
}

function renderStage() {
  if (!parts || !$("stage")) return;
  const done = Math.min(seen.size, parts);
  $("stage").textContent = copy().stage.replace("{n}", String(Math.max(1, done))).replace("{total}", String(parts));
  const marks = $("stage-marks");
  if (!marks) return;
  if (marks.childElementCount !== parts) {
    marks.replaceChildren();
    for (let i = 0; i < parts; i++) marks.append(document.createElement("i"));
  }
  [...marks.children].forEach((mark, i) => mark.classList.toggle("done", i < done));
}

function renderClock() {
  const left = Math.max(0, budgetEndsAt - performance.now());
  const seconds = Math.ceil(left / 1000);
  const box = $("clock");
  if (!box) return;
  $("clock-time").textContent = seconds >= 60
    ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`
    : `${seconds}s`;
  box.classList.toggle("urgent", left <= URGENT_MS);
}

function nudge(instructions) {
  if (finished || agentWs?.readyState !== WebSocket.OPEN) return;
  holdFloor();
  agentWs.send(JSON.stringify({ type: "reply.create", instructions }));
}

function theyStopped() {
  // Only ever armed once they have actually said something.
  clearTimeout(afterSpeaking);
  afterSpeaking = setTimeout(() => {
    afterSpeaking = null;
    nudge("The candidate finished answering five seconds ago and is waiting. Take your turn now: "
      + "either one follow-up built on what they just said, or the next question, built on it as well.");
  }, AFTER_SPEAKING_MS);
}

function timeIsUp() {
  budgetTimer = null;
  nudge("The candidate has been answering for a minute and a half, which is as long as one answer gets. "
    + "Take the turn now. Acknowledge them in at most four words, do not mention the time, and ask your "
    + "next question built on what they have just said.");
}

function setSpeaking(on) {
  speaking = on;
  $("mic")?.classList.toggle("speaking", on);
  $("state-label").textContent = on ? copy().speaking : copy().listening;
  if (on) pushLevel(0);
}

// -- the agent's events -------------------------------------------------------------------

function handleAgent(message) {
  switch (message.type) {
    case "session.ready":
      // The stored agent has no fixed greeting: a recorded one could not be
      // translated. It opens the interview itself, in the chosen language.
      startAudio().then(() => {
        show("interview");
        renderStage();
        agentWs.send(JSON.stringify({ type: "reply.create",
          instructions: "Open the interview now: greet in one short sentence, then ask the warm-up question." }));
      });
      break;
    case "reply.audio":
      playAgentAudio(message.data);
      break;
    case "transcript.agent":
      agentSpoke = Boolean(message.text);
      addTurn("them", message.text);
      break;
    case "transcript.user":
      addTurn("you", message.text);
      break;
    case "input.speech.started":
      player?.port.postMessage("flush");   // barge-in: stop the half-spoken sentence
      lastEvent = "input.speech.started";
      clearTimeout(afterSpeaking);  // they are talking again; the budget keeps running
      afterSpeaking = null;
      break;
    case "input.speech.stopped":
      // Start measuring the answer now rather than when the agent asks for it:
      // by the time the tool call arrives the verdict is already waiting, and the
      // pause between an answer and the next question is a beat, not a wait.
      lastEvent = "input.speech.stopped";
      assessmentFor();
      theyStopped();
      break;
    case "reply.started":
      lastEvent = "reply.started";
      holdFloor();
      break;
    case "reply.done":
      lastEvent = "reply.done";
      // The interviewer has stopped: whatever is said from now on is the answer.
      // A reply that said nothing out loud - the silent one that follows a tool
      // result - must not cut the answer in two.
      if (agentSpoke) {
        answerStartMs = clockMs();
        giveTheFloor();     // the floor is theirs, and it stays theirs for five seconds
      }
      agentSpoke = false;
      flushResults();
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
  const { building, answerWords, sent, verdict } = await assessmentFor();
  if (building) {
    warmupWords = sent;                                   // keep what has been said so far
    if (verdict.baseline_ready) baselineWords = sent;     // long enough to compare against
  }
  seen.add(topic);
  renderStage();
  // answer_words, not words: the verdict carries a word COUNT under that name and
  // the spread below would quietly replace the list with it - which is how the
  // first reports were built with no answers in them.
  assessments.push({ topic_id: topic, claim: call.arguments?.claim ?? "", ...verdict, answer_words: answerWords });
  queueResult(call.call_id, { instruction: verdict.instruction, verdict: verdict.verdict });
  // The interview has used up its questions. The agent has been told to thank the
  // candidate and end; if it asks one more instead, the page ends it anyway. A
  // limit a model can talk itself out of is not a limit.
  if (verdict.last && !lastCallTimer) {
    $("clock")?.setAttribute("hidden", "");
    lastCallTimer = setTimeout(finish, LAST_WORD_MS);
  }
}

// The assessment of one answer, computed once. It starts the moment the candidate
// stops speaking, so by the time the agent asks for it the verdict is usually
// already waiting: the pause between an answer and the next question is a beat
// rather than a wait.
function assessmentFor() {
  // Keyed on which answer this is, not on when it started. Two answers can share
  // a start - the clock runs on audio sent, and it does not move while nothing is
  // being sent - and reusing one answer's verdict for the next is silent and
  // wrong. A turn number cannot collide.
  const id = turnId;
  const start = answerStartMs;
  if (assessing && assessing.id === id) {
    return assessing.promise.then((done) => {
      // The pause that started it was a thinking pause and the candidate carried
      // on: that assessment was made on half an answer, so it is made again.
      if (words.length === done.seen) return done;
      assessing = { id, promise: assessAnswer(start, id) };
      return assessing.promise;
    });
  }
  assessing = { id, promise: assessAnswer(start, id) };
  return assessing.promise;
}

async function assessAnswer(start, id) {
  const building = !baselineWords;
  // One assessment per answer, so counting answers counts questions asked. Keyed
  // on the turn, so an assessment redone after a thinking pause does not count
  // the question twice.
  answered.add(id);
  const asked = answered.size;
  await settle(start);
  const answerWords = words.filter((w) => w.start >= start);
  // While the baseline is still being gathered, what gets assessed is everything
  // the candidate has said so far in the warm-up, not just the last sentence.
  const sent = building ? warmupWords.concat(answerWords) : answerWords;
  let verdict;
  try {
    const response = await fetch("/api/assess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer_words: sent, baseline_words: building ? null : baselineWords, asked }),
    });
    verdict = await response.json();
    if (!response.ok) throw new Error(verdict.detail || `HTTP ${response.status}`);
  } catch (error) {
    // A failed assessment must not derail the interview: the agent carries on,
    // and it still carries on from the candidate's own words.
    verdict = {
      verdict: "not_measured",
      instruction: "Ask one short question built on what the candidate just said, quoting a phrase of "
        + "theirs word for word.",
      error: error.message,
    };
  }
  return { building, answerWords, sent, verdict, seen: words.length };
}

// Give the transcription connection a moment to finalise the last words of the
// answer: it settles a beat after the agent's own turn detection fires.
function settle(start) {
  return new Promise((resolve) => {
    const quick = performance.now() + WORDS_SETTLE_MS;
    // An answer that arrives with no words at all is the expensive failure: it
    // cannot be compared, and it costs a question. Waiting longer for the first
    // word than for the last is worth the beat it adds.
    const patient = performance.now() + WORDS_SETTLE_MS * 3;
    const tick = () => {
      const heard = words.some((w) => w.start >= start);
      const now = performance.now();
      if (heard ? (now - lastWordAt > 250 || now > quick) : now > patient) resolve();
      else setTimeout(tick, 60);
    };
    tick();
  });
}

function queueResult(callId, result) {
  pendingResults.push({ call_id: callId, result });
  flushResults();
  // This is the interview's one deadlock. The agent will not speak again until it
  // has the result of the tool it called, and the result was only ever sent when
  // "reply.done" happened to be the last event. One cough from the candidate
  // during the assessment made "input.speech.started" the last event instead, and
  // the reply that would have cleared it could never arrive. The order is still
  // preferred; it is no longer waited on indefinitely.
  clearTimeout(flushTimer);
  flushTimer = setTimeout(() => flushResults(true), RESULT_GRACE_MS);
}

function flushResults(force = false) {
  if (!pendingResults.length || agentWs?.readyState !== WebSocket.OPEN) return;
  if (!force && lastEvent !== "reply.done") return;
  clearTimeout(flushTimer);
  flushTimer = null;
  for (const pending of pendingResults) {
    agentWs.send(JSON.stringify({ type: "tool.result", call_id: pending.call_id, result: JSON.stringify(pending.result) }));
  }
  pendingResults = [];
}

// -- the conversation on screen ------------------------------------------------------------

let held = null;   // the question now shown large, kept out of the history below it

function addTurn(role, text) {
  if (!text) return;
  turns.push({ role: role === "you" ? "candidate" : "interviewer", text, at: Math.round(clockMs()) });
  if (role === "them") {
    // The question stays large while it is being answered, and drops into the
    // history only once the interviewer has asked the next one.
    if (held) writeTurn("them", held);
    held = text;
    $("said").textContent = text;
    return;
  }
  writeTurn(role, text);
}

function writeTurn(role, text) {
  const line = document.createElement("p");
  line.className = `turn ${role}`;
  line.append(Object.assign(document.createElement("span"), { textContent: role === "you" ? copy().you : copy().them }), text);
  $("transcript").prepend(line);   // newest first, right under the question being asked
}

// -- the end ---------------------------------------------------------------------------------

async function finish() {
  if (finished) return;
  finished = true;
  clearTimeout(lastCallTimer);
  holdFloor();
  show("saving");
  stream?.getTracks().forEach((track) => track.stop());
  setTimeout(() => agentWs?.readyState === WebSocket.OPEN && agentWs.send(JSON.stringify({ type: "session.end" })), 200);
  if (sttWs?.readyState === WebSocket.OPEN) sttWs.send(JSON.stringify({ type: "Terminate" }));

  try {
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recordedAt: new Date().toISOString(), language, invite, turns, assessments, words }),
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
