// L'assistente del sito (SPEC F17-F20): risponde su TPI e previsione, con i soli numeri dei dati del sito.
// Fornitore a scelta con un'impostazione (F18): ognuno con il suo formato. Claude con la libreria ufficiale.
import Anthropic from "@anthropic-ai/sdk";

const NUMERI_DEL_METODO = [450, 900, 1500, 25, 80, 38, 90];   // soglie scritte nel metodo: si possono citare

// ---- F20: si manda solo ciò che serve alla domanda (meno dati = più veloce e più economico) ----
const normalizza = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const parti = (nome) => normalizza(nome).split(/[\s-]+/).filter((p) => p.length > 3);
const nominati = (dati, testo) => { const q = normalizza(testo || ""); return dati.giocatori.filter((g) => parti(g.nome).some((p) => q.includes(p))); };
export function scegliGiocatori(dati, domanda, perRuolo = 10) {
  const migliori = ["ATT", "CEN", "DIF"].flatMap((r) => dati.giocatori.filter((g) => g.ruolo === r).sort((a, b) => b.pred - a.pred).slice(0, perRuolo));
  return [...new Set([...nominati(dati, domanda), ...migliori, ...dati.giocatori.filter((g) => g.sottovalutato)])];
}

// ---- il prompt di sistema: regole (F19) + i giocatori scelti per la domanda (F20) ----
export function costruisciSistema(dati, domanda) {
  const v = dati.verdetto;
  const scelti = domanda === undefined ? dati.giocatori : scegliGiocatori(dati, domanda);
  const righe = scelti.map((g) => JSON.stringify(g)).join("\n");
  return [
    "Sei l'assistente di Football Scout Index, un sito che descrive i giocatori (TPI) e prevede il loro rendimento",
    `della stagione ${dati.stagione_prevista} (gol senza rigori + assist attesi per 90 minuti).`,
    "Regole, senza eccezioni:",
    "1. Ogni numero che scrivi (TPI, previsione, minuti, età, statistiche) deve venire solo dai dati qui sotto. Mai un numero che non c'è.",
    "2. Puoi usare la tua conoscenza generale del calcio solo per dare contesto, senza numeri, e scrivendo sempre \"(conoscenza generale, non verificata)\".",
    "3. Niente notizie: rinnovi, mercato, infortuni di oggi, voci. Rispondi: \"Questo non è nei miei dati.\"",
    `4. In questo campionato la previsione ${v.mostra_previsione ? "ha passato la prova" : "NON ha ancora passato la prova: dillo sempre quando citi una previsione"}`
      + ` (previsione ${v.mod} contro statistica semplice ${v.grezzo}). La lista dei giovani sottovalutati ${v.mostra_sottovalutati ? "ha passato la prova" : "non ha passato la prova: non presentarla come affidabile"}.`,
    "5. Rispondi nella lingua della domanda, in modo breve e semplice.",
    "",
    "Campi: nome, squadra, ruolo (ATT/CEN/DIF), eta, tpi (stagione in corso), pred (previsione per 90'), lo/hi (forbice all'80%),",
    "prima (rendimento per 90' la stagione prima), minuti (la stagione prima), sottovalutato (giovane con pochi minuti, previsione alta).",
    `Dati del campionato (${dati.lega}): i giocatori nominati nella domanda, i primi 10 per ruolo e i giovani sottovalutati`,
    "(se chiedono di un giocatore che non è qui sotto, di' che non è fra quelli con una previsione).",
    righe,
  ].join("\n");
}

// ---- C21: ogni numero della risposta deve esistere nei dati ----
function valori(oggetto, out = []) {
  if (typeof oggetto === "number") out.push(oggetto);
  else if (oggetto && typeof oggetto === "object") Object.values(oggetto).forEach((v) => valori(v, out));
  return out;
}
const squadre = (dati) => [...new Set(dati.giocatori.map((g) => g.squadra).filter((s) => s && /\d/.test(s)))]
  .map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
const CONTEGGI = Array.from({ length: 10 }, (_, i) => i + 1);   // "tre difensori", "i primi 5": conteggi, non dati

// Frase per frase: se la frase nomina dei giocatori, i suoi numeri devono essere i loro (o del verdetto, o del
// metodo); se non ne nomina, basta che esistano nei dati. Così un numero attribuito al giocatore sbagliato si vede.
export function verificaNumeri(testo, dati) {
  const comuni = valori(dati.verdetto || {}).concat(NUMERI_DEL_METODO, CONTEGGI);
  const tutti = valori(dati).concat(NUMERI_DEL_METODO, CONTEGGI);
  const inventati = [];
  for (const frase of testo.split(/(?<=[.!?;\n])\s+/)) {
    const chi = nominati(dati, frase);
    const ammessi = chi.length ? valori(chi).concat(comuni) : tutti;
    const pulita = frase
      .replace(/\b\d{4}[-/]\d{2,4}\b/g, " ")                          // le stagioni (2026-27) non sono dati da verificare
      .replace(/(^|\n)\s*\d{1,2}[.)]\s/g, "$1 ")                       // i numeri degli elenchi (1. 2. 3.)
      .replace(new RegExp(squadre(dati).join("|") || "$^", "g"), " ");  // numeri dentro i nomi (Parma Calcio 1913)
    for (const m of pulita.matchAll(/-?\d+(?:[.,]\d+)?/g)) {
      const scritto = m[0], x = parseFloat(scritto.replace(",", ".")), dec = (scritto.split(/[.,]/)[1] || "").length;
      const c = 10 ** dec;
      if (!ammessi.some((v) => Math.round(v * c) / c === x || (dec === 0 && Math.floor(v) === x))) inventati.push(scritto);
    }
  }
  return { ok: inventati.length === 0, inventati };
}

// ---- C23: un adattatore per fornitore, scelto con l'impostazione PROVIDER ----
async function postJson(fetchFn, url, headers, corpo) {
  const r = await fetchFn(url, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(corpo) });
  if (!r.ok) throw new Error(`fornitore: risposta ${r.status}`);
  return r.json();
}
const ADATTATORI = {
  async anthropic(env, sistema, domanda, deps) {
    const client = deps.anthropic || new Anthropic({ apiKey: env.API_KEY, ...(env.BASE_URL ? { baseURL: env.BASE_URL } : {}) });
    const r = await client.beta.messages.create({
      model: env.MODEL || "claude-opus-5-5",
      max_tokens: 16000,
      output_config: { effort: "low" },                       // domande brevi: poco ragionamento basta
      system: [{ type: "text", text: sistema, cache_control: { type: "ephemeral" } }],   // i dati restano in cache
      messages: [{ role: "user", content: domanda }],
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",                                   // se il modello rifiuta, il server prova un altro modello
    });
    if (r.stop_reason === "refusal") return "Su questa domanda non posso rispondere.";
    return r.content.filter((b) => b.type === "text").map((b) => b.text).join("");
  },
  async openai(env, sistema, domanda, deps) {
    const r = await postJson(deps.fetch, `${env.BASE_URL || "https://api.openai.com/v1"}/chat/completions`,
      { authorization: `Bearer ${env.API_KEY}` },
      { model: env.MODEL, messages: [{ role: "system", content: sistema }, { role: "user", content: domanda }] });
    return r.choices[0].message.content;
  },
  // Groq: il suo formato nativo è Chat Completions (lo stesso di OpenAI), con il suo indirizzo
  async groq(env, sistema, domanda, deps) {
    return ADATTATORI.openai({ ...env, BASE_URL: env.BASE_URL || "https://api.groq.com/openai/v1" }, sistema, domanda, deps);
  },
  async gemini(env, sistema, domanda, deps) {
    const base = env.BASE_URL || "https://generativelanguage.googleapis.com/v1beta";
    const r = await postJson(deps.fetch, `${base}/models/${env.MODEL}:generateContent`, { "x-goog-api-key": env.API_KEY },
      { systemInstruction: { parts: [{ text: sistema }] }, contents: [{ role: "user", parts: [{ text: domanda }] }] });
    return r.candidates[0].content.parts.map((p) => p.text || "").join("");
  },
  async ollama(env, sistema, domanda, deps) {
    const r = await postJson(deps.fetch, `${env.BASE_URL || "http://127.0.0.1:11434"}/api/chat`, {},
      { model: env.MODEL, stream: false, options: { num_ctx: parseInt(env.CONTESTO || "8192", 10) },   // i dati non entrano nei 2.048 di serie
        messages: [{ role: "system", content: sistema }, { role: "user", content: domanda }] });
    return r.message.content.replace(/<think>[\s\S]*?<\/think>/g, "").trim();   // i modelli che "ragionano" (deepseek-r1)
  },
};
export async function chiamaModello(env, sistema, domanda, deps = {}) {
  const adattatore = ADATTATORI[env.PROVIDER];
  if (!adattatore) throw new Error(`PROVIDER sconosciuto: ${env.PROVIDER} (anthropic, openai, groq, gemini, ollama)`);
  return adattatore(env, sistema, domanda, { fetch: globalThis.fetch, ...deps });
}

// ---- una domanda: tetto giornaliero (C24) -> dati -> modello -> controllo dei numeri (C21) ----
export async function rispondi(richiesta, env, deps) {
  const domanda = String(richiesta.domanda || "").slice(0, 600);
  if (!domanda.trim()) return { stato: 400, corpo: { risposta: "Scrivi una domanda." } };
  if (env.QUOTA && env.LIMITE_GIORNALIERO) {
    const chiave = `q:${new Date().toISOString().slice(0, 10)}`;
    const usate = parseInt((await env.QUOTA.get(chiave)) || "0", 10);
    if (usate >= parseInt(env.LIMITE_GIORNALIERO, 10)) return { stato: 429, corpo: { risposta: "Limite di domande raggiunto per oggi: riprova domani." } };
    await env.QUOTA.put(chiave, String(usate + 1), { expirationTtl: 172800 });
  }
  const dati = await deps.dati(richiesta.lega);
  const risposta = await chiamaModello(env, costruisciSistema(dati), domanda, deps);
  const controllo = verificaNumeri(risposta, dati);
  return { stato: 200, corpo: { risposta, numeri_ok: controllo.ok, numeri_non_trovati: controllo.inventati } };
}
