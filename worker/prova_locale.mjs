// Prova vera dell'assistente con un modello (C21, C22): domande fisse, controllo dei numeri di ogni risposta.
// Uso: node prova_locale.mjs [quante]   — PROVIDER/MODEL/BASE_URL/API_KEY dalle variabili d'ambiente (di serie: Ollama locale)
import { readFileSync, writeFileSync } from "node:fs";
import { rispondi } from "./src/assistente.js";

import { homedir } from "node:os";
// la chiave: dalla variabile API_KEY o da un file fuori dal progetto (CHIAVE_FILE), mai scritta qui
const chiave = process.env.API_KEY || (process.env.CHIAVE_FILE ? readFileSync(process.env.CHIAVE_FILE.replace("~", homedir()), "utf8").trim() : undefined);
const env = { PROVIDER: process.env.PROVIDER || "ollama", MODEL: process.env.MODEL || "qwen2.5:3b",
              BASE_URL: process.env.BASE_URL, API_KEY: chiave, CONTESTO: process.env.CONTESTO };
const domande = JSON.parse(readFileSync(new URL("./domande_prova.json", import.meta.url), "utf8"));
const quante = parseInt(process.argv[2] || String(domande.length), 10);
const dati = (lega) => JSON.parse(readFileSync(new URL(`../uscita/${lega}/assistente.json`, import.meta.url), "utf8"));
const esiti = [];
const PAUSA = parseInt(process.env.PAUSA || "0", 10) * 1000;   // secondi fra una domanda e l'altra (limiti dei piani gratuiti)
for (const d of domande.slice(0, quante)) {
  if (PAUSA && esiti.length) await new Promise((r) => setTimeout(r, PAUSA));
  const t0 = Date.now();
  let corpo;
  try { ({ corpo } = await rispondi({ domanda: d.domanda, lega: d.lega }, env, { dati: async (l) => dati(l) })); }
  catch (e) { corpo = { risposta: `ERRORE: ${e.message}`, numeri_ok: false, numeri_non_trovati: [] }; }
  const notizia_ok = d.tipo !== "notizia" || /non è nei miei dati|not in my data/i.test(corpo.risposta);
  esiti.push({ ...d, ...corpo, notizia_ok, secondi: Math.round((Date.now() - t0) / 1000) });
  console.log(`${corpo.numeri_ok && notizia_ok ? "OK " : "NO "} [${d.lega}] ${d.domanda}\n    -> ${corpo.risposta.replace(/\s+/g, " ").slice(0, 220)}`
    + (corpo.numeri_ok ? "" : `\n    numeri non nei dati: ${corpo.numeri_non_trovati.join(", ")}`));
}
const ok = esiti.filter((e) => e.numeri_ok && e.notizia_ok).length;
console.log(`\n${ok} risposte su ${esiti.length} rispettano le regole (${env.PROVIDER} ${env.MODEL}).`);
writeFileSync(new URL(`../prove/assistente_${env.PROVIDER}_${env.MODEL.replace(/[^a-z0-9.-]/gi, "-")}.json`, import.meta.url), JSON.stringify({ env: { PROVIDER: env.PROVIDER, MODEL: env.MODEL }, ok, totale: esiti.length, esiti }, null, 1));
