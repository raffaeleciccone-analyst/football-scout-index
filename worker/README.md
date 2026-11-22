# Assistente di Football Scout Index

Risponde alle domande dei visitatori su TPI e previsione (SPEC F17-F20). Tiene la chiave API sul server: il browser
parla solo con questo Worker.

## Fornitori (C23)
Si sceglie con `PROVIDER` in `wrangler.toml`, ognuno nel suo formato:

| PROVIDER | Formato | Esempio di MODEL |
|---|---|---|
| `anthropic` | libreria ufficiale `@anthropic-ai/sdk` (con il "piano B" del server se il modello rifiuta) | `claude-opus-5-5` |
| `openai` | Chat Completions | il modello OpenAI scelto |
| `gemini` | `generateContent` | il modello Gemini scelto |
| `ollama` | `/api/chat` (anche sul PC, senza chiave) | `qwen2.5:3b` |

## Regole (F19, C21-C22)
- Ogni numero della risposta viene cercato nei dati del sito, frase per frase: se la frase nomina un giocatore, i numeri
  devono essere i suoi. Se un numero non si trova, la risposta arriva con l'avviso e il sito lo mostra.
- Niente notizie: "Questo non è nei miei dati."
- Si mandano al modello solo i giocatori che servono: i nominati, i primi 10 per ruolo, i giovani sottovalutati (F20).

## Provarlo
- Test (fornitori finti, nessun costo): `npm test`
- Prova vera sulle 30 domande di `domande_prova.json`: `node prova_locale.mjs` (di serie Ollama sul PC; per un altro
  fornitore: `PROVIDER=anthropic API_KEY=... node prova_locale.mjs`). Il risultato va in `prove/assistente_<fornitore>.json`.
- Chat nell'anteprima del sito: `node locale.mjs`, poi rigenerare il sito con `FSI_ASSISTENTE_URL=http://127.0.0.1:8792/chat`.

## Pubblicarlo (quando si decide)
`npx wrangler login`, `npx wrangler kv namespace create QUOTA` (id in `wrangler.toml`), `npx wrangler secret put API_KEY`,
`npx wrangler deploy`. Poi l'indirizzo del Worker va in `FSI_ASSISTENTE_URL` e il sito si rigenera.
