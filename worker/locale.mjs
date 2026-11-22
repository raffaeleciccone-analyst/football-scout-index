// L'assistente sul PC, per provarlo nell'anteprima del sito senza Cloudflare: stessa logica del Worker.
// Uso: node locale.mjs   (di serie Ollama qwen2.5:3b; PROVIDER/MODEL/API_KEY/BASE_URL dalle variabili d'ambiente)
// Poi rigenera il sito con FSI_ASSISTENTE_URL=http://127.0.0.1:8792/chat
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { rispondi } from "./src/assistente.js";

const env = { PROVIDER: process.env.PROVIDER || "ollama", MODEL: process.env.MODEL || "qwen2.5:3b",
              BASE_URL: process.env.BASE_URL, API_KEY: process.env.API_KEY };
const dati = async (lega) => JSON.parse(readFileSync(new URL(`../uscita/${lega}/assistente.json`, import.meta.url), "utf8"));
const LEGHE = new Set(["serie_a", "premier"]);

createServer(async (req, res) => {
  res.setHeader("access-control-allow-origin", "http://127.0.0.1:8791");
  res.setHeader("access-control-allow-headers", "content-type");
  if (req.method === "OPTIONS") return res.end();
  let corpo = "";
  for await (const pezzo of req) corpo += pezzo;
  try {
    const richiesta = JSON.parse(corpo);
    if (!LEGHE.has(richiesta.lega)) throw new Error("lega");
    const r = await rispondi(richiesta, env, { dati });
    res.writeHead(r.stato, { "content-type": "application/json" }).end(JSON.stringify(r.corpo));
  } catch {
    res.writeHead(502, { "content-type": "application/json" }).end(JSON.stringify({ risposta: "L'assistente non risponde in questo momento." }));
  }
}).listen(8792, "127.0.0.1", () => console.log(`assistente locale su http://127.0.0.1:8792/chat (${env.PROVIDER} ${env.MODEL})`));
