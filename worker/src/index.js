// Worker Cloudflare dell'assistente: tiene la chiave API sul server (F17, C24). Il browser parla solo con lui.
// Impostazioni (wrangler.toml / segreti): PROVIDER, MODEL, BASE_URL, DATI_URL, LIMITE_GIORNALIERO, ORIGINE;
// segreto API_KEY (wrangler secret put API_KEY: non finisce mai in un file); KV QUOTA per il tetto giornaliero.
import { rispondi } from "./assistente.js";

const LEGHE = new Set(["serie_a", "premier"]);

export default {
  async fetch(req, env) {
    const cors = { "access-control-allow-origin": env.ORIGINE || "*", "access-control-allow-methods": "POST, OPTIONS",
                   "access-control-allow-headers": "content-type" };
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "POST" || new URL(req.url).pathname !== "/chat") return new Response("non trovato", { status: 404, headers: cors });
    let richiesta;
    try { richiesta = await req.json(); } catch { return Response.json({ risposta: "Richiesta non valida." }, { status: 400, headers: cors }); }
    if (!LEGHE.has(richiesta.lega)) return Response.json({ risposta: "Campionato sconosciuto." }, { status: 400, headers: cors });
    try {
      const { stato, corpo } = await rispondi(richiesta, env, {
        dati: async (lega) => (await fetch(`${env.DATI_URL}/${lega}/assistente.json`, { cf: { cacheTtl: 3600 } })).json(),
      });
      return Response.json(corpo, { status: stato, headers: cors });
    } catch (e) {
      return Response.json({ risposta: "L'assistente non risponde in questo momento: riprova più tardi." }, { status: 502, headers: cors });
    }
  },
};
