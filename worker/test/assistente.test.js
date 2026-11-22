// Fase 4 — assistente: SPEC F17-F20; criteri C21-C24. Fornitori finti: nessuna chiamata vera, nessun costo.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { costruisciSistema, verificaNumeri, chiamaModello, rispondi, scegliGiocatori } from "../src/assistente.js";

const DATI = {
  lega: "serie_a", stagione_prevista: "2026-27",
  verdetto: { mostra_previsione: false, mostra_sottovalutati: true, mod: 0.754, grezzo: 0.738 },
  giocatori: [
    { nome: "Lautaro Martínez", squadra: "Inter", ruolo: "ATT", eta: 29, tpi: 1.17, pred: 0.62, prima: 0.71, minuti: 2600 },
    { nome: "Ange-Yoan Bonny", squadra: "Inter", ruolo: "ATT", eta: 22, pred: 0.47, prima: 0.62, minuti: 1112, sottovalutato: true },
  ],
};

// ---- C21: ogni numero della risposta esiste nei dati ----
test("C21 numeri presenti nei dati: ok", () => {
  assert.equal(verificaNumeri("Lautaro ha un TPI di 1,17 e la previsione dice 0.62.", DATI).ok, true);
});
test("C21 un numero inventato viene trovato", () => {
  const v = verificaNumeri("Lautaro farà 0,95 per 90 minuti.", DATI);
  assert.equal(v.ok, false);
  assert.deepEqual(v.inventati, ["0,95"]);
});
test("C21 un numero vero ma del giocatore sbagliato viene trovato", () => {
  const v = verificaNumeri("Bonny ha un TPI di 1,17.", DATI);   // 1,17 è il TPI di Lautaro, non di Bonny
  assert.equal(v.ok, false);
});
test("C21 elenchi, conteggi e numeri nei nomi delle squadre non sono dati", () => {
  const d = { ...DATI, giocatori: DATI.giocatori.concat([{ nome: "Lautaro Valenti", squadra: "Parma Calcio 1913", ruolo: "DIF", pred: 0.08 }]) };
  assert.equal(verificaNumeri("Ecco tre attaccanti:\n1. Lautaro Martínez: 0,62\n2. Bonny: 0,47\nValenti gioca nel Parma Calcio 1913.", d).ok, true);
  assert.equal(verificaNumeri("Lautaro Martínez ha giocato 3087 minuti.", d).ok, false);   // minuti inventati
});
test("F20 si mandano i nominati, i primi per ruolo e i giovani, non tutto", () => {
  const molti = { ...DATI, giocatori: Array.from({ length: 100 }, (_, i) => ({ nome: `Giocatore${i} Cognome${i}`, ruolo: "ATT", pred: i / 100 })) };
  molti.giocatori.push({ nome: "Zeta Rarissimo", ruolo: "DIF", pred: 0.01 });
  const scelti = scegliGiocatori(molti, "Come va Rarissimo?");
  assert.ok(scelti.some((g) => g.nome === "Zeta Rarissimo"));
  assert.ok(scelti.length <= 12);
});
test("C21 stagioni e numeri del metodo non contano come inventati", () => {
  assert.equal(verificaNumeri("Nella stagione 2026-27, con almeno 450 minuti, Bonny ha 22 anni.", DATI).ok, true);
});

// ---- C22: le regole sono nel prompt ----
test("C22 il prompt vieta notizie e numeri non nei dati, e segna la conoscenza generale", () => {
  const s = costruisciSistema(DATI);
  assert.match(s, /non è nei miei dati/);
  assert.match(s, /non verificat/);
  assert.match(s, /solo .*dati/i);
  assert.match(s, /Bonny/);   // F20: tutti i giocatori, non solo i primi
});

// ---- C23: cambiare fornitore = cambiare un'impostazione ----
function fetchFinto(registro, risposta) {
  return async (url, opz) => { registro.push({ url, corpo: JSON.parse(opz.body), headers: opz.headers }); return { ok: true, status: 200, json: async () => risposta }; };
}
test("C23 openai: formato Chat Completions", async () => {
  const reg = [];
  const t = await chiamaModello({ PROVIDER: "openai", MODEL: "m", API_KEY: "k", BASE_URL: "https://x/v1" }, "sis", "dom",
    { fetch: fetchFinto(reg, { choices: [{ message: { content: "ciao" } }] }) });
  assert.equal(t, "ciao");
  assert.equal(reg[0].url, "https://x/v1/chat/completions");
  assert.equal(reg[0].corpo.messages[0].role, "system");
});
test("C23 groq: formato Chat Completions al suo indirizzo", async () => {
  const reg = [];
  await chiamaModello({ PROVIDER: "groq", MODEL: "m", API_KEY: "k" }, "sis", "dom", { fetch: fetchFinto(reg, { choices: [{ message: { content: "ciao" } }] }) });
  assert.equal(reg[0].url, "https://api.groq.com/openai/v1/chat/completions");
  assert.equal(reg[0].headers.authorization, "Bearer k");
});
test("C23 gemini: formato generateContent, chiave nell'intestazione", async () => {
  const reg = [];
  const t = await chiamaModello({ PROVIDER: "gemini", MODEL: "g", API_KEY: "k" }, "sis", "dom",
    { fetch: fetchFinto(reg, { candidates: [{ content: { parts: [{ text: "ciao" }] } }] }) });
  assert.equal(t, "ciao");
  assert.match(reg[0].url, /models\/g:generateContent$/);
  assert.equal(reg[0].headers["x-goog-api-key"], "k");
  assert.equal(reg[0].corpo.systemInstruction.parts[0].text, "sis");
});
test("C23 ollama: formato /api/chat, senza chiave", async () => {
  const reg = [];
  const t = await chiamaModello({ PROVIDER: "ollama", MODEL: "qwen2.5:3b", BASE_URL: "http://127.0.0.1:11434" }, "sis", "dom",
    { fetch: fetchFinto(reg, { message: { content: "ciao" } }) });
  assert.equal(t, "ciao");
  assert.equal(reg[0].url, "http://127.0.0.1:11434/api/chat");
  assert.equal(reg[0].corpo.stream, false);
});
test("C23 anthropic: libreria ufficiale, rifiuto gestito", async () => {
  const chiamate = [];
  const clienteFinto = { beta: { messages: { create: async (p) => { chiamate.push(p); return { stop_reason: "end_turn", content: [{ type: "text", text: "ciao" }] }; } } } };
  const t = await chiamaModello({ PROVIDER: "anthropic", MODEL: "claude-opus-5-5", API_KEY: "k" }, "sis", "dom", { anthropic: clienteFinto });
  assert.equal(t, "ciao");
  assert.equal(chiamate[0].model, "claude-opus-5-5");
  assert.equal(chiamate[0].fallbacks, "default");
  const rifiuto = { beta: { messages: { create: async () => ({ stop_reason: "refusal", content: [] }) } } };
  assert.match(await chiamaModello({ PROVIDER: "anthropic", MODEL: "m", API_KEY: "k" }, "s", "d", { anthropic: rifiuto }), /non posso rispondere/);
});

// ---- C24: tetto giornaliero e nessuna chiave nei file ----
test("C24 oltre il tetto: 'limite raggiunto' e nessuna chiamata al modello", async () => {
  let chiamato = false;
  const kv = { get: async () => "50", put: async () => {} };
  const r = await rispondi({ domanda: "ciao", lega: "serie_a" }, { QUOTA: kv, LIMITE_GIORNALIERO: "50", PROVIDER: "openai" },
    { dati: async () => DATI, fetch: async () => { chiamato = true; } });
  assert.equal(r.stato, 429);
  assert.match(r.corpo.risposta, /limite/i);
  assert.equal(chiamato, false);
});
test("C24 nessuna chiave API scritta nei file del progetto", () => {
  const radice = join(import.meta.dirname, "..", "..");
  const chiave = /(sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AIza[0-9A-Za-z_-]{30,})/;
  const salta = new Set(["node_modules", ".git", "dati", "uscita", "__pycache__", ".pytest_cache"]);
  const guarda = (d) => readdirSync(d).forEach((n) => {
    const p = join(d, n);
    if (salta.has(n)) return;
    if (statSync(p).isDirectory()) return guarda(p);
    if (/\.(js|json|py|html|toml|md|txt|bat|css)$/.test(n)) assert.doesNotMatch(readFileSync(p, "utf8"), chiave, p);
  });
  guarda(radice);
});
