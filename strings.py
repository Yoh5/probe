"""Probe - the report, in the language the interview was held in.

A candidate answers in their own language and the recruiter reads the result, so
the report follows the interview rather than the reader's browser. Everything the
report page shows lives here, including its structural labels: the page renders
what it is handed and holds no English of its own, which is the only arrangement
where a missing translation is visible instead of silently falling back.

`{n}`, `{total}` and `{compared}` are filled in by report.py.
"""
from __future__ import annotations

# The four signals, by the name detector.py knows them by. Each is a label, the
# unit it is really in, and whether it is a ratio against the candidate's own
# warm-up or a rate.
SIGNAL_KINDS = {
    "long_word_share/base": "ratio",
    "disfluency_rate": "rate",
    "comma_rate/base": "ratio",
    "mean_run/base": "ratio",
}

STRINGS = {
    "en": {
        "scale": "Every measured answer on one line",
        "scale_note": "One number per answer, from four signals compared with this candidate's own warm-up. The only thing that matters is which side of the line it falls.",
        "scale_left": "sounds thought through",
        "scale_right": "sounds prepared",
        "head_thin": "Only {compared} of {total} answers could be compared.",
        "report_title": "Interview report",
        "dig": "Dig into this",
        "answers": "The interview, answer by answer ({compared} of {total} could be compared)",
        "limits": "What this report cannot tell you",
        "spoken": "The interview, as it was spoken",
        "chain": "How the next question was chosen",
        "measured": "The code measured",
        "decided": "The code decided",
        "told": "The code told the interviewer",
        "then_asked": "The interviewer then asked",
        "chain_note": "The language model never saw these numbers and never chose the instruction. "
                      "It chose the wording of the question.",
        "candidate": "Candidate",
        "interviewer": "Interviewer",
        "stat_answers": "answers",
        "stat_compared": "compared",
        "stat_prepared": "sound prepared",
        "stat_words": "words spoken",
        "what_they_said": "What they said",
        "closing_words": "Closing words of the answer",
        "come_away": "Come away knowing: ",
        "not_recorded": "Question {n} - not recorded with this interview",
        "worth_second_look": "Worth a second look",
        "nothing_flagged": "Nothing flagged",
        "nothing_comparable": "Nothing comparable",
        "all_interviews": "All interviews",
        "fact_words": "words",
        "fact_seconds": "seconds",
        "fact_rate": "words a minute",

        "verdict_prepared": "Sounds prepared",
        "verdict_spontaneous": "Sounds thought through on the spot",
        "verdict_not_measured": "Too short to compare",
        "verdict_baseline": "Warm-up, used as the comparison",
        "summary_prepared": "worth asking about again, in person",
        "summary_spontaneous": "nothing here suggests a rehearsed answer",
        "summary_not_measured": "not enough speech to say anything either way",
        "summary_baseline": "this is what the other answers were compared against",

        "step_prepared": "Ask for the parts a rehearsal does not contain",
        "why_prepared": "This answer came out polished. That is not misconduct and it is not a "
                        "finding about the candidate - it is a sign that the ground underneath it "
                        "was not tested.",
        "step_not_measured": "Not covered - ask it again",
        "why_not_measured": "There was not enough here to go on. The topic is still open.",
        "step_missed": "Never came up",
        "why_missed": "The interview ran out of questions before reaching this.",

        "head_one": "One thing to dig into at the next interview.",
        "head_many": "{n} things to dig into at the next interview.",
        "head_clear": "Nothing here needs a second look.",
        "head_empty": "This interview produced nothing to go on.",

        "signal_long_word_share/base": "Long words",
        "signal_disfluency_rate": "Hesitations and restarts",
        "signal_comma_rate/base": "Clause breaks",
        "signal_mean_run/base": "Words between pauses",
        "unit_ratio": "against their own warm-up",
        "unit_rate": "per 100 words",

        "reason_long_word_share/base": "vocabulary closer to written text than in the warm-up",
        "reason_disfluency_rate": "few hesitations, repeated words or restarts",
        "reason_comma_rate/base": "fewer run-on clauses than in the warm-up",
        "reason_mean_run/base": "longer stretches of words without a pause than in the warm-up",

        "limit_delivery": "This measures how an answer was delivered, never whether it was true, "
                          "and never whether the candidate is any good at the job.",
        "limit_reasons": "An answer can sound prepared because the candidate rehearsed, because "
                         "they have told the story many times, or because that is how they speak. "
                         "The report cannot tell those apart, and neither can anyone else from a "
                         "recording.",
        "limit_notes": "Reading from notes is not misconduct. Treat a flag as something to ask "
                       "about, never as a reason to reject.",
        "limit_fitted": "The detector was fitted on {answers} labelled answers from {who}, and the "
                        "signals were chosen after looking at that data. It has not been tested on "
                        "a speaker it was not fitted on.",
        "limit_accuracy": "Held out one session at a time, it was right {percent}% of the time. It "
                          "will be wrong about some answers here.",
        "one_speaker": "one speaker",
        "many_speakers": "{n} speakers",
    },
    "fr": {
        "scale": "Chaque réponse mesurée sur une même échelle",
        "scale_note": "Un nombre par réponse, à partir de quatre signaux comparés à l'échauffement du candidat. Seul compte le côté de la ligne où il tombe.",
        "scale_left": "sonne pensée sur le moment",
        "scale_right": "sonne préparée",
        "head_thin": "Seules {compared} réponses sur {total} ont pu être comparées.",
        "report_title": "Compte rendu d'entretien",
        "dig": "À creuser",
        "answers": "L'entretien, réponse par réponse ({compared} sur {total} ont pu être comparées)",
        "limits": "Ce que ce compte rendu ne peut pas vous dire",
        "spoken": "L'entretien, tel qu'il a été parlé",
        "chain": "Comment la question suivante a été choisie",
        "measured": "Le code a mesuré",
        "decided": "Le code a décidé",
        "told": "Le code a dit à l'entretien",
        "then_asked": "L'entretien a alors demandé",
        "chain_note": "Le modèle de langage n'a jamais vu ces chiffres et n'a jamais choisi "
                      "l'instruction. Il a choisi la formulation de la question.",
        "candidate": "Candidat",
        "interviewer": "Entretien",
        "stat_answers": "réponses",
        "stat_compared": "comparées",
        "stat_prepared": "sonnent préparées",
        "stat_words": "mots prononcés",
        "what_they_said": "Ce qu'il a dit",
        "closing_words": "Derniers mots de la réponse",
        "come_away": "Ce qu'il faut en retirer : ",
        "not_recorded": "Question {n} - non enregistrée avec cet entretien",
        "worth_second_look": "À revoir de plus près",
        "nothing_flagged": "Rien à signaler",
        "nothing_comparable": "Rien de comparable",
        "all_interviews": "Tous les entretiens",
        "fact_words": "mots",
        "fact_seconds": "secondes",
        "fact_rate": "mots par minute",

        "verdict_prepared": "Sonne préparée",
        "verdict_spontaneous": "Sonne pensée sur le moment",
        "verdict_not_measured": "Trop courte pour être comparée",
        "verdict_baseline": "Échauffement, sert de référence",
        "summary_prepared": "à reprendre de vive voix",
        "summary_spontaneous": "rien ici n'évoque une réponse répétée",
        "summary_not_measured": "pas assez de parole pour se prononcer dans un sens ou dans l'autre",
        "summary_baseline": "c'est à cela que les autres réponses ont été comparées",

        "step_prepared": "Demandez ce qu'une répétition ne contient pas",
        "why_prepared": "Cette réponse est sortie polie. Ce n'est ni une faute ni un jugement sur "
                        "le candidat : c'est le signe que le terrain en dessous n'a pas été testé.",
        "step_not_measured": "Pas couvert - reposez la question",
        "why_not_measured": "Il n'y avait pas assez de matière. Le sujet reste ouvert.",
        "step_missed": "Jamais abordé",
        "why_missed": "L'entretien a épuisé ses questions avant d'y arriver.",

        "head_one": "Une chose à creuser au prochain entretien.",
        "head_many": "{n} choses à creuser au prochain entretien.",
        "head_clear": "Rien ici ne demande un second regard.",
        "head_empty": "Cet entretien n'a rien produit d'exploitable.",

        "signal_long_word_share/base": "Mots longs",
        "signal_disfluency_rate": "Hésitations et reprises",
        "signal_comma_rate/base": "Ruptures de proposition",
        "signal_mean_run/base": "Mots entre deux pauses",
        "unit_ratio": "par rapport à son échauffement",
        "unit_rate": "pour 100 mots",

        "reason_long_word_share/base": "vocabulaire plus proche de l'écrit qu'à l'échauffement",
        "reason_disfluency_rate": "peu d'hésitations, de répétitions ou de reprises",
        "reason_comma_rate/base": "moins de propositions à rallonge qu'à l'échauffement",
        "reason_mean_run/base": "enchaînements plus longs sans pause qu'à l'échauffement",

        "limit_delivery": "Ceci mesure la façon dont une réponse a été livrée, jamais si elle était "
                          "vraie, et jamais si le candidat est bon pour le poste.",
        "limit_reasons": "Une réponse peut sonner préparée parce que le candidat a répété, parce "
                         "qu'il a raconté cette histoire cent fois, ou simplement parce qu'il parle "
                         "ainsi. Le compte rendu ne peut pas les distinguer, et personne ne le peut "
                         "à partir d'un enregistrement.",
        "limit_notes": "Lire ses notes n'est pas une faute. Traitez un signalement comme une "
                       "question à poser, jamais comme un motif de rejet.",
        "limit_fitted": "Le détecteur a été calibré sur {answers} réponses annotées provenant de "
                        "{who}, et les signaux ont été choisis après avoir regardé ces données. Il "
                        "n'a pas été testé sur un locuteur sur lequel il n'a pas été calibré.",
        "limit_accuracy": "En laissant une session de côté à chaque fois, il a eu raison {percent} % "
                          "du temps. Il se trompera sur certaines réponses ici.",
        "one_speaker": "un seul locuteur",
        "many_speakers": "{n} locuteurs",
    },
    "es": {
        "scale": "Cada respuesta medida en una misma escala",
        "scale_note": "Un número por respuesta, a partir de cuatro señales comparadas con el calentamiento del propio candidato. Solo importa de qué lado de la línea cae.",
        "scale_left": "suena pensada en el momento",
        "scale_right": "suena preparada",
        "head_thin": "Solo {compared} de {total} respuestas pudieron compararse.",
        "report_title": "Informe de la entrevista",
        "dig": "Para profundizar",
        "answers": "La entrevista, respuesta por respuesta ({compared} de {total} pudieron compararse)",
        "limits": "Lo que este informe no puede decirle",
        "spoken": "La entrevista, tal como se habló",
        "chain": "Cómo se eligió la siguiente pregunta",
        "measured": "El código midió",
        "decided": "El código decidió",
        "told": "El código le dijo a la entrevista",
        "then_asked": "La entrevista preguntó entonces",
        "chain_note": "El modelo de lenguaje nunca vio estos números ni eligió la instrucción. "
                      "Eligió cómo formular la pregunta.",
        "candidate": "Candidato",
        "interviewer": "Entrevista",
        "stat_answers": "respuestas",
        "stat_compared": "comparadas",
        "stat_prepared": "suenan preparadas",
        "stat_words": "palabras dichas",
        "what_they_said": "Lo que dijo",
        "closing_words": "Últimas palabras de la respuesta",
        "come_away": "Qué hay que averiguar: ",
        "not_recorded": "Pregunta {n} - no registrada con esta entrevista",
        "worth_second_look": "Merece una segunda mirada",
        "nothing_flagged": "Nada que señalar",
        "nothing_comparable": "Nada comparable",
        "all_interviews": "Todas las entrevistas",
        "fact_words": "palabras",
        "fact_seconds": "segundos",
        "fact_rate": "palabras por minuto",

        "verdict_prepared": "Suena preparada",
        "verdict_spontaneous": "Suena pensada en el momento",
        "verdict_not_measured": "Demasiado corta para comparar",
        "verdict_baseline": "Calentamiento, sirve de referencia",
        "summary_prepared": "conviene retomarlo en persona",
        "summary_spontaneous": "nada aquí sugiere una respuesta ensayada",
        "summary_not_measured": "no hay suficiente habla para decir nada en un sentido ni en otro",
        "summary_baseline": "con esto se compararon las demás respuestas",

        "step_prepared": "Pida lo que un ensayo no contiene",
        "why_prepared": "Esta respuesta salió pulida. No es una falta ni un juicio sobre el "
                        "candidato: es señal de que el terreno que hay debajo no se puso a prueba.",
        "step_not_measured": "Sin cubrir - vuelva a preguntarlo",
        "why_not_measured": "No había suficiente material. El tema sigue abierto.",
        "step_missed": "Nunca salió",
        "why_missed": "La entrevista agotó sus preguntas antes de llegar aquí.",

        "head_one": "Una cosa que profundizar en la próxima entrevista.",
        "head_many": "{n} cosas que profundizar en la próxima entrevista.",
        "head_clear": "Nada aquí pide una segunda mirada.",
        "head_empty": "Esta entrevista no produjo nada aprovechable.",

        "signal_long_word_share/base": "Palabras largas",
        "signal_disfluency_rate": "Vacilaciones y reinicios",
        "signal_comma_rate/base": "Cortes de oración",
        "signal_mean_run/base": "Palabras entre pausas",
        "unit_ratio": "frente a su propio calentamiento",
        "unit_rate": "por 100 palabras",

        "reason_long_word_share/base": "vocabulario más cercano a la lengua escrita que en el calentamiento",
        "reason_disfluency_rate": "pocas vacilaciones, repeticiones o reinicios",
        "reason_comma_rate/base": "menos oraciones encadenadas que en el calentamiento",
        "reason_mean_run/base": "tramos más largos de palabras sin pausa que en el calentamiento",

        "limit_delivery": "Esto mide cómo se dijo una respuesta, nunca si era cierta, y nunca si el "
                          "candidato vale para el puesto.",
        "limit_reasons": "Una respuesta puede sonar preparada porque el candidato ensayó, porque ha "
                         "contado esa historia muchas veces, o simplemente porque habla así. El "
                         "informe no puede distinguirlo, y nadie puede hacerlo desde una grabación.",
        "limit_notes": "Leer notas no es una falta. Trate un aviso como algo que preguntar, nunca "
                       "como un motivo para rechazar.",
        "limit_fitted": "El detector se ajustó con {answers} respuestas etiquetadas de {who}, y las "
                        "señales se eligieron tras mirar esos datos. No se ha probado con un "
                        "hablante con el que no se ajustó.",
        "limit_accuracy": "Dejando fuera una sesión cada vez, acertó el {percent} % de las veces. Se "
                          "equivocará con algunas respuestas de aquí.",
        "one_speaker": "un solo hablante",
        "many_speakers": "{n} hablantes",
    },
    "de": {
        "scale": "Jede gemessene Antwort auf einer Skala",
        "scale_note": "Eine Zahl je Antwort, aus vier Signalen im Vergleich zum eigenen Aufwärmen der Person. Es zählt nur, auf welcher Seite der Linie sie liegt.",
        "scale_left": "klingt im Moment gedacht",
        "scale_right": "klingt vorbereitet",
        "head_thin": "Nur {compared} von {total} Antworten waren vergleichbar.",
        "report_title": "Gesprächsbericht",
        "dig": "Hier nachhaken",
        "answers": "Das Gespräch, Antwort für Antwort ({compared} von {total} vergleichbar)",
        "limits": "Was dieser Bericht nicht sagen kann",
        "spoken": "Das Gespräch, wie es gesprochen wurde",
        "chain": "Wie die nächste Frage gewählt wurde",
        "measured": "Der Code hat gemessen",
        "decided": "Der Code hat entschieden",
        "told": "Der Code sagte dem Gespräch",
        "then_asked": "Das Gespräch fragte daraufhin",
        "chain_note": "Das Sprachmodell hat diese Zahlen nie gesehen und die Anweisung nie gewählt. "
                      "Es hat die Formulierung der Frage gewählt.",
        "candidate": "Kandidat",
        "interviewer": "Gespräch",
        "stat_answers": "Antworten",
        "stat_compared": "verglichen",
        "stat_prepared": "klingen vorbereitet",
        "stat_words": "gesprochene Wörter",
        "what_they_said": "Was gesagt wurde",
        "closing_words": "Letzte Worte der Antwort",
        "come_away": "Das gilt es herauszufinden: ",
        "not_recorded": "Frage {n} - nicht mit diesem Gespräch aufgezeichnet",
        "worth_second_look": "Einen zweiten Blick wert",
        "nothing_flagged": "Nichts auffällig",
        "nothing_comparable": "Nichts Vergleichbares",
        "all_interviews": "Alle Gespräche",
        "fact_words": "Wörter",
        "fact_seconds": "Sekunden",
        "fact_rate": "Wörter pro Minute",

        "verdict_prepared": "Klingt vorbereitet",
        "verdict_spontaneous": "Klingt im Moment gedacht",
        "verdict_not_measured": "Zu kurz zum Vergleichen",
        "verdict_baseline": "Aufwärmen, dient als Vergleich",
        "summary_prepared": "im persönlichen Gespräch noch einmal aufgreifen",
        "summary_spontaneous": "nichts hier deutet auf eine eingeübte Antwort hin",
        "summary_not_measured": "zu wenig gesprochen, um in eine Richtung etwas zu sagen",
        "summary_baseline": "damit wurden die übrigen Antworten verglichen",

        "step_prepared": "Fragen Sie nach dem, was eine Probe nicht enthält",
        "why_prepared": "Diese Antwort kam glatt heraus. Das ist kein Fehlverhalten und kein Urteil "
                        "über die Person - es heißt, dass der Boden darunter nie geprüft wurde.",
        "step_not_measured": "Nicht abgedeckt - noch einmal fragen",
        "why_not_measured": "Es gab zu wenig, woran man sich halten konnte. Das Thema bleibt offen.",
        "step_missed": "Kam nie zur Sprache",
        "why_missed": "Dem Gespräch gingen die Fragen aus, bevor es hierher kam.",

        "head_one": "Eine Sache, bei der im nächsten Gespräch nachzuhaken ist.",
        "head_many": "{n} Dinge, bei denen im nächsten Gespräch nachzuhaken ist.",
        "head_clear": "Nichts hier braucht einen zweiten Blick.",
        "head_empty": "Dieses Gespräch hat nichts Brauchbares ergeben.",

        "signal_long_word_share/base": "Lange Wörter",
        "signal_disfluency_rate": "Zögern und Neuansätze",
        "signal_comma_rate/base": "Satzbrüche",
        "signal_mean_run/base": "Wörter zwischen Pausen",
        "unit_ratio": "gegenüber dem eigenen Aufwärmen",
        "unit_rate": "pro 100 Wörter",

        "reason_long_word_share/base": "Wortwahl näher an der Schriftsprache als beim Aufwärmen",
        "reason_disfluency_rate": "wenig Zögern, Wiederholungen oder Neuansätze",
        "reason_comma_rate/base": "weniger aneinandergereihte Teilsätze als beim Aufwärmen",
        "reason_mean_run/base": "längere Wortfolgen ohne Pause als beim Aufwärmen",

        "limit_delivery": "Dies misst, wie eine Antwort vorgetragen wurde, nie ob sie wahr war, und "
                          "nie ob die Person für die Stelle taugt.",
        "limit_reasons": "Eine Antwort kann vorbereitet klingen, weil geübt wurde, weil die "
                         "Geschichte schon oft erzählt wurde, oder weil jemand einfach so spricht. "
                         "Der Bericht kann das nicht unterscheiden, und aus einer Aufnahme kann es "
                         "sonst auch niemand.",
        "limit_notes": "Vom Blatt zu lesen ist kein Fehlverhalten. Behandeln Sie einen Hinweis als "
                       "etwas, wonach zu fragen ist, nie als Grund für eine Absage.",
        "limit_fitted": "Der Detektor wurde auf {answers} gekennzeichnete Antworten von {who} "
                        "angepasst, und die Signale wurden nach Sicht auf diese Daten gewählt. Er "
                        "wurde nie an einer Stimme geprüft, auf die er nicht angepasst wurde.",
        "limit_accuracy": "Bei jeweils einer ausgelassenen Sitzung lag er in {percent} % der Fälle "
                          "richtig. Bei einigen Antworten hier wird er falsch liegen.",
        "one_speaker": "einer einzigen Stimme",
        "many_speakers": "{n} Stimmen",
    },
    "it": {
        "scale": "Ogni risposta misurata su una sola scala",
        "scale_note": "Un numero per risposta, da quattro segnali confrontati con il riscaldamento del candidato stesso. Conta solo da che parte della linea cade.",
        "scale_left": "suona pensata sul momento",
        "scale_right": "suona preparata",
        "head_thin": "Solo {compared} risposte su {total} sono state confrontabili.",
        "report_title": "Resoconto del colloquio",
        "dig": "Da approfondire",
        "answers": "Il colloquio, risposta per risposta ({compared} su {total} confrontabili)",
        "limits": "Che cosa questo resoconto non può dirle",
        "spoken": "Il colloquio, così come è stato parlato",
        "chain": "Come è stata scelta la domanda successiva",
        "measured": "Il codice ha misurato",
        "decided": "Il codice ha deciso",
        "told": "Il codice ha detto al colloquio",
        "then_asked": "Il colloquio ha allora chiesto",
        "chain_note": "Il modello linguistico non ha mai visto questi numeri e non ha mai scelto "
                      "l'istruzione. Ha scelto come formulare la domanda.",
        "candidate": "Candidato",
        "interviewer": "Colloquio",
        "stat_answers": "risposte",
        "stat_compared": "confrontate",
        "stat_prepared": "suonano preparate",
        "stat_words": "parole dette",
        "what_they_said": "Che cosa ha detto",
        "closing_words": "Ultime parole della risposta",
        "come_away": "Che cosa capire: ",
        "not_recorded": "Domanda {n} - non registrata con questo colloquio",
        "worth_second_look": "Merita un secondo sguardo",
        "nothing_flagged": "Nulla da segnalare",
        "nothing_comparable": "Nulla di confrontabile",
        "all_interviews": "Tutti i colloqui",
        "fact_words": "parole",
        "fact_seconds": "secondi",
        "fact_rate": "parole al minuto",

        "verdict_prepared": "Suona preparata",
        "verdict_spontaneous": "Suona pensata sul momento",
        "verdict_not_measured": "Troppo breve per confrontarla",
        "verdict_baseline": "Riscaldamento, usato come riferimento",
        "summary_prepared": "da riprendere di persona",
        "summary_spontaneous": "nulla qui fa pensare a una risposta provata",
        "summary_not_measured": "non c'è abbastanza parlato per dire nulla né in un senso né nell'altro",
        "summary_baseline": "è con questo che sono state confrontate le altre risposte",

        "step_prepared": "Chieda quello che una prova non contiene",
        "why_prepared": "Questa risposta è uscita levigata. Non è una colpa né un giudizio sulla "
                        "persona: è il segno che il terreno sotto non è stato messo alla prova.",
        "step_not_measured": "Non coperto - lo richieda",
        "why_not_measured": "Non c'era abbastanza materia. L'argomento resta aperto.",
        "step_missed": "Non è mai venuto fuori",
        "why_missed": "Il colloquio ha esaurito le domande prima di arrivarci.",

        "head_one": "Una cosa da approfondire al prossimo colloquio.",
        "head_many": "{n} cose da approfondire al prossimo colloquio.",
        "head_clear": "Nulla qui chiede un secondo sguardo.",
        "head_empty": "Questo colloquio non ha prodotto nulla di utilizzabile.",

        "signal_long_word_share/base": "Parole lunghe",
        "signal_disfluency_rate": "Esitazioni e riprese",
        "signal_comma_rate/base": "Interruzioni di frase",
        "signal_mean_run/base": "Parole tra due pause",
        "unit_ratio": "rispetto al suo riscaldamento",
        "unit_rate": "ogni 100 parole",

        "reason_long_word_share/base": "lessico più vicino allo scritto che nel riscaldamento",
        "reason_disfluency_rate": "poche esitazioni, ripetizioni o riprese",
        "reason_comma_rate/base": "meno frasi a catena che nel riscaldamento",
        "reason_mean_run/base": "sequenze di parole senza pausa più lunghe che nel riscaldamento",

        "limit_delivery": "Questo misura come una risposta è stata detta, mai se fosse vera, e mai "
                          "se il candidato vada bene per il ruolo.",
        "limit_reasons": "Una risposta può suonare preparata perché il candidato ha provato, perché "
                         "ha raccontato quella storia molte volte, o semplicemente perché parla "
                         "così. Il resoconto non può distinguerli, e da una registrazione non può "
                         "farlo nessuno.",
        "limit_notes": "Leggere dagli appunti non è una colpa. Tratti una segnalazione come "
                       "qualcosa da chiedere, mai come un motivo per scartare.",
        "limit_fitted": "Il rilevatore è stato tarato su {answers} risposte etichettate di {who}, e "
                        "i segnali sono stati scelti dopo aver guardato quei dati. Non è stato "
                        "provato su una voce su cui non è stato tarato.",
        "limit_accuracy": "Lasciando fuori una sessione alla volta, ha avuto ragione nel {percent} % "
                          "dei casi. Su alcune risposte qui sbaglierà.",
        "one_speaker": "un solo parlante",
        "many_speakers": "{n} parlanti",
    },
    "pt": {
        "scale": "Cada resposta medida numa só escala",
        "scale_note": "Um número por resposta, a partir de quatro sinais comparados com o aquecimento do próprio candidato. Só conta de que lado da linha cai.",
        "scale_left": "soa pensada no momento",
        "scale_right": "soa preparada",
        "head_thin": "Apenas {compared} de {total} respostas puderam ser comparadas.",
        "report_title": "Relatório da entrevista",
        "dig": "A aprofundar",
        "answers": "A entrevista, resposta a resposta ({compared} de {total} puderam ser comparadas)",
        "limits": "O que este relatório não lhe pode dizer",
        "spoken": "A entrevista, tal como foi falada",
        "chain": "Como a pergunta seguinte foi escolhida",
        "measured": "O código mediu",
        "decided": "O código decidiu",
        "told": "O código disse à entrevista",
        "then_asked": "A entrevista perguntou então",
        "chain_note": "O modelo de linguagem nunca viu estes números nem escolheu a instrução. "
                      "Escolheu a forma de fazer a pergunta.",
        "candidate": "Candidato",
        "interviewer": "Entrevista",
        "stat_answers": "respostas",
        "stat_compared": "comparadas",
        "stat_prepared": "soam preparadas",
        "stat_words": "palavras ditas",
        "what_they_said": "O que disse",
        "closing_words": "Últimas palavras da resposta",
        "come_away": "O que é preciso saber: ",
        "not_recorded": "Pergunta {n} - não registada com esta entrevista",
        "worth_second_look": "Merece um segundo olhar",
        "nothing_flagged": "Nada a assinalar",
        "nothing_comparable": "Nada comparável",
        "all_interviews": "Todas as entrevistas",
        "fact_words": "palavras",
        "fact_seconds": "segundos",
        "fact_rate": "palavras por minuto",

        "verdict_prepared": "Soa preparada",
        "verdict_spontaneous": "Soa pensada no momento",
        "verdict_not_measured": "Curta demais para comparar",
        "verdict_baseline": "Aquecimento, serve de referência",
        "summary_prepared": "vale a pena retomar pessoalmente",
        "summary_spontaneous": "nada aqui sugere uma resposta ensaiada",
        "summary_not_measured": "fala insuficiente para dizer o que quer que seja",
        "summary_baseline": "foi com isto que as outras respostas foram comparadas",

        "step_prepared": "Peça aquilo que um ensaio não contém",
        "why_prepared": "Esta resposta saiu polida. Não é falta nem juízo sobre o candidato: é "
                        "sinal de que o terreno por baixo nunca foi posto à prova.",
        "step_not_measured": "Por cobrir - volte a perguntar",
        "why_not_measured": "Não havia matéria suficiente. O tema continua em aberto.",
        "step_missed": "Nunca surgiu",
        "why_missed": "A entrevista esgotou as perguntas antes de lá chegar.",

        "head_one": "Uma coisa a aprofundar na próxima entrevista.",
        "head_many": "{n} coisas a aprofundar na próxima entrevista.",
        "head_clear": "Nada aqui pede um segundo olhar.",
        "head_empty": "Esta entrevista não produziu nada de aproveitável.",

        "signal_long_word_share/base": "Palavras longas",
        "signal_disfluency_rate": "Hesitações e recomeços",
        "signal_comma_rate/base": "Cortes de oração",
        "signal_mean_run/base": "Palavras entre pausas",
        "unit_ratio": "face ao seu próprio aquecimento",
        "unit_rate": "por 100 palavras",

        "reason_long_word_share/base": "vocabulário mais próximo da escrita do que no aquecimento",
        "reason_disfluency_rate": "poucas hesitações, repetições ou recomeços",
        "reason_comma_rate/base": "menos orações encadeadas do que no aquecimento",
        "reason_mean_run/base": "sequências de palavras sem pausa mais longas do que no aquecimento",

        "limit_delivery": "Isto mede como uma resposta foi dita, nunca se era verdadeira, e nunca se "
                          "o candidato serve para o lugar.",
        "limit_reasons": "Uma resposta pode soar preparada porque o candidato ensaiou, porque já "
                         "contou aquilo muitas vezes, ou simplesmente porque fala assim. O relatório "
                         "não os distingue, e a partir de uma gravação mais ninguém o faz.",
        "limit_notes": "Ler pelos apontamentos não é falta. Trate um aviso como algo a perguntar, "
                       "nunca como motivo para recusar.",
        "limit_fitted": "O detetor foi ajustado com {answers} respostas anotadas de {who}, e os "
                        "sinais foram escolhidos depois de olhar para esses dados. Não foi testado "
                        "numa voz com que não tenha sido ajustado.",
        "limit_accuracy": "Deixando de fora uma sessão de cada vez, acertou {percent} % das vezes. "
                          "Vai errar em algumas respostas aqui.",
        "one_speaker": "um único falante",
        "many_speakers": "{n} falantes",
    },
}
