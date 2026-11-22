# Football Scout Index — PIANO (come)

> Il COSA sta in SPEC.md (approvata il 22/11/2026). Qui c'è il COME.
> Ogni scelta cita la frase della spec che la giustifica. Se il piano contraddice la spec, vince la spec.
> Stile: ponytail (V2): prima "serve?", poi "c'è già?", poi libreria standard, poi dipendenza già installata.

Stato: **APPROVATO il 22/11/2026** (Q1 = contesti tenuti, proposta A; Q2 = repository privata)

## 1. Architettura

```
 FONTI                     PORTA D'INGRESSO           CALCOLO                 USCITE
 Understat ──raccolta──┐                          ┌─ tpi.py ────────┐
 heXI (età) ───────────┼──> database SQLite ──> controlli ─┤                 ├─> sito/ (JSON + HTML, IT/EN)
 Transfermarkt (inf.) ─┘   (formato unico)          └─ previsione.py ─┘        └─> dataset assistente
 MySQL vecchio ──ponte─┘   (sola lettura)                                      pubblica.py ──> GitHub Pages
                                                                              worker/ ──> modello IA (fornitore a scelta)
```

## 2. Porta d'ingresso: il database nuovo

Tutto il calcolo legge **solo** il database nuovo (un file SQLite). Lo riempiono due "riempitori" che producono
**lo stesso formato**:
- **ponte.py** (subito): copia dal MySQL di oggi, in sola lettura. Permette di costruire TPI, previsione e sito
  adesso, con Understat giù. Motivo: F23.
- **raccolta.py** (dopo): scarica dalle fonti. Il test C26 confronta le righe che produce con quelle del ponte;
  al cambio (F24) il ponte si cancella.

Tabelle (una riga = un fatto, la stagione è **sempre** una colonna, mai dedotta):

| Tabella | Contenuto | Perché (spec) |
|---|---|---|
| `partite` | lega, stagione, giornata, data, casa, trasferta, gol, xG (con rigori) | F1 (SOS, xG squadra), C2 |
| `righe` | lega, stagione, partita, giocatore, squadra *di quella partita*, avversario, posizione Understat, minuti, gol, gol senza rigori, assist, tiri, xG, npxG, xA, buildup, chain | F1-F4, C26 |
| `giocatori` | id Understat, nome, data di nascita | F2 (età), F13 |
| `infortuni` | giocatore, stagione, inizio, rientro, giorni fuori | F2 (ingrediente), D12-D13 |
| `correzioni_ruolo` | giocatore, stagione, ruolo (le correzioni a mano di SPEC_INDICE C5) | F1, F5 |

### Scelte e motivi
- **SQLite (libreria standard), non MySQL.** Motivo: F22 (database proprio), C27 (il vecchio non si tocca), e i test
  creano un database da zero in un attimo. Ponytail: nessun server in più.
- **La chiave del giocatore è l'id Understat**, non nome+squadra. Motivo: i doppioni del motore vecchio nascevano lì
  (SPEC_DATI D1); C26.
- **3 decimali per xG/xA** (come deciso in SPEC_DATI Q1). Motivo: C26, C1.
- **Storico che non si riscarica** (infortuni passati, correzioni di ruolo, date di nascita mancanti): il ponte lo
  copia una volta; la raccolta poi lo aggiorna. Motivo: F21 senza perdere dati (ponytail: mai perdere dati).

## 3. Calcolo

### 3a. TPI (F1)
- `tpi.py` nasce da `C:\dev\_ricostruzione\indice3\indice.py` (244 righe, già identico al pubblicato: Spearman 1,000).
  Ponytail: si riusa quello che c'è e funziona. Cambia solo l'ingresso (database invece dei CSV).
- **Ogni funzione riceve la stagione e filtra per quella** (una sola funzione `righe(lega, stagione, fino_a_giornata)`
  legge i dati). Motivo: C2, C4 (P8 e P9 del vecchio erano stagioni mescolate).
- **Tutti i pesi e le soglie in `config.py`**, e la pagina del metodo li legge da lì. Motivo: C3, F16.
- **I 5 contesti si calcolano** (F1b, Q1 = A). La regola si **ricava dal codice di oggi** (parte1_analisi.py) e si
  scrive per intero in SPEC_CONTESTI (dentro questa repository), chiudendo i punti che C13 lasciava aperti:
  shrinkage, K della centralità (nel payload cresce quando le presenze calano: `k_ctx`), effetto squadra (nei
  contesti è assente), SOS del contesto, parità per le "prime 6". Si verifica sul campo `ctx` del payload
  2025-26 (C3b), esportato in `tests/fixtures/`.
- **Ingredienti di contesto nella previsione**: "TPI contro le prime 6 meno TPI totale" e "casa meno trasferta",
  con lo stesso tiraggio verso la media (pochi minuti → vicino a zero). Restano nel modello solo se la prova a
  gruppi (e poi quella vera) migliora; il metodo scrive l'esito. Motivo: F1b, C3c.

### 3b. Previsione (F2-F10)
- **Il rivale dei sottovalutati (C10) e il cuore del modello sono la stessa formula**: output "tirato" verso la
  media del ruolo, `(output × minuti + media_ruolo × K) / (minuti + K)`, con **K stimato sui dati** (si prova una
  griglia di K e si tiene quello che prevede meglio sulle stagioni di addestramento). Motivo: F6 (chi gioca poco va
  verso la media), C7, C10.
- **Modello = regressione lineare con penalità (ridge)** su: output tirato, minuti (log), età e età², tendenza
  (seconda metà meno prima metà della stagione), giorni di infortunio, ruolo, lega. Pesi stimati con scikit-learn
  (già installato) o numpy. Motivo: F2 ("pesi stimati dai dati"), C5. Niente modelli complicati: con ~400 giocatori
  per stagione una regressione è quello che i dati reggono.
- **Serie A e Premier stimate insieme** (con la lega come ingrediente: il doppio dei dati), **prova separata per
  lega**: ogni sito mostra la previsione solo se ha passato la prova *nel suo campionato*. Motivo: F9, C8.
- **Chi si valuta nella prova**: chi ha ≥ 450' nella stagione di partenza (F7) e ≥ 900' in quella prevista (come
  V23: sotto i 900' il rendimento reale è troppo rumoroso per fare da metro). Motivo: C8, confronto con V23.
- **"Batte" (C8)**: bootstrap appaiato sui giocatori (2.000 ricampionamenti, numpy) della differenza di ρ di
  Spearman; batte se l'intervallo 5°-95° sta tutto sopra zero.
- **Forbice (F6, C11)**: dai residui di addestramento, con un'ampiezza che cresce quando i minuti calano
  (scala ∝ √(1/minuti) stimata sui dati); forbice = 10°-90° percentile. Si mostra solo se sulla prova ne cattura fra
  il 70% e il 90%.
- **Motivi (F13, C15)**: contributo di ogni ingrediente = peso × (valore del giocatore − media del ruolo); si
  mostrano i 2-3 più grandi in valore assoluto, con frasi da `testi.json`.
- **Previsione aggiornata (F10, C14)**: lo stesso modello con un ingrediente in più, l'output della stagione in corso
  fino alla giornata k (tirato con lo stesso K). Si prova "tagliando" una stagione passata alla giornata k, per
  k = 5, 10, 15, 19, 25, 30; fra un punto e l'altro vale la prova del punto prima. La previsione di agosto è un file
  scritto una volta (`previsione_agosto_<stagione>.json`) e mai riscritto. Motivo: C14.
- **Stagioni (C5, C13)**:
  - *oggi* (una coppia sola, 24-25 → 25-26): prova "a metà" (giocatori divisi in 5 gruppi, stimo su 4 e provo sul
    quinto). Tutto è marcato **"prototipo, non verificato"**;
  - *con la 2023-24*: stima su 23-24 → 24-25, **prova vera** su 24-25 → 25-26. Solo allora la parola "verificata".
  - per la previsione pubblicata (agosto 2027 → 2027-28) si ristima su tutte le coppie.
- **Il TPI Pro come rivale (D2 → deciso così)**: serve **solo sulla stagione di prova** (2024-25), e i suoi numeri
  2024-25 esistono già per tutti e due i campionati (`payload_2024-25_full.json`, campo `tpi_ext`). Si esportano
  una volta in `tests/fixtures/rivali/` e non si riscrive il TPI Pro. Ponytail: un modello scartato non si
  ricostruisce. Motivo: F8, C12.
- **Valore di mercato (D5 → deciso: non si usa)**: esiste solo il file di fine stagione della rosa heXI, quindi
  usarlo per prevedere vorrebbe dire sbirciare nel futuro (C4). Nel codice resta un commento
  `shortcut: niente valore di mercato, servono foto datate ad agosto; se le si salva per 2 stagioni, riprovare`.
- **Costruzione (F4)**: stesso modello e stessa prova, con il buildup per 90 al posto dell'output, solo DIF e CEN.
- *(fase 2, dettagli decisi scrivendo il codice)*
  - **"Output grezzo"** = la stessa misura dell'obiettivo (gol senza rigori + xA per 90) nella stagione di partenza,
    come nella V23. Fra gli ingredienti del modello c'è anche xG senza rigori + xA per 90 (più stabile dei gol).
  - **Il rendimento reale** della stagione dopo si somma su Serie A e Premier (chi cambia campionato fra le due resta
    nella prova: la chiave è l'id Understat).
  - **Previsione aggiornata, finché manca la 2023-24**: alla giornata k gli ingredienti vengono dalla stagione in corso
    tagliata a k (non c'è ancora la "stagione prima" completa da affiancare). La soglia dei 450' si riduce in
    proporzione (450 × k / giornate) — `shortcut:` con la 2023-24 si affianca la stagione prima completa e la soglia
    torna 450'.
  - **Infortuni**: fuori dal modello in questo giro (nessun dato 2024-25, vedi §9b).

## 4. Sito (F11-F16, F19)
- **Pagine statiche generate da Python**: i dati in JSON, l'HTML da modelli con jinja2 (già installato). Niente
  framework JavaScript: un file JS piccolo per ricerca, lingua e grafici. Motivo: F12 (poche pagine), ponytail.
- **Un file `sito/testi.json`** con ogni testo in `it` e `en`; il pulsante IT/EN cambia tutti i testi della pagina.
  Un test fallisce se un testo manca in una lingua. Motivo: F15, C17.
- **Le frasi con numeri sono modelli** ("ρ {rho} contro {rho_grezzo}"), riempiti dai risultati. Motivo: F16, C18.
- **Una sola pagina giocatore** `giocatore.html?id=…` che legge il JSON. Motivo: F13, C19.
- **Home comune** in una repository sua (`football-scout-index`, GitHub Pages); i due siti nelle loro repository di
  oggi. Motivo: F11, D3.
- **Fino al cambio tutto finisce in `uscita/`** dentro questa repository (esclusa da git). Motivo: V8, C28.

## 5. Assistente (F17-F20)
- **Un Worker Cloudflare nuovo, piccolo**, che parla in due "lingue": Anthropic e formato OpenAI (che copre OpenAI,
  Gemini, Mistral, DeepSeek, OpenRouter, Ollama). Fornitore, indirizzo e modello sono **impostazioni** del Worker
  (`PROVIDER`, `BASE_URL`, `MODEL`). Si riprende l'idea del Worker di oggi, non il codice. Motivo: F18, C23.
- **Dati**: il JSON della lega con **tutti** i giocatori con previsione, solo le colonne utili (~350 righe). Si manda
  il file della lega del sito da cui arriva la domanda; con la cache dei prompt costa poco.
  `shortcut: si manda tutta la lega; se il costo per domanda supera il tetto, mandare solo i giocatori citati`.
  Motivo: F20.
- **Regole nel prompt** (F19) e **controllo automatico**: una funzione estrae i numeri dalla risposta e verifica che
  esistano nei dati. Il test C21 (30 domande vere) costa chiamate al modello: si lancia a mano, non a ogni giro.
- Chiave solo come segreto del Worker, tetto giornaliero come oggi. Motivo: F17, C24.

## 6. Controlli, raccolta, pubblicazione (F21-F24)
- **controlli.py**: le regole D2-D13 di SPEC_DATI riscritte sullo schema nuovo (D1 sparisce quasi tutta: con la chiave
  id Understat i doppioni d'anagrafica non possono nascere; resta il controllo "un id, una persona"). Motivo: C25.
- **raccolta.py**: Understat con **soccerdata** (già installato, è quello che usa il motore di oggi). Età da heXI, infortuni
  dalla pagina Transfermarkt degli infortunati, come oggi. Le **170 partite salvate in ~/soccerdata** (2026-27) si
  copiano in `tests/fixtures/understat/` e fanno da fonte finta per i test. Motivo: F23, C26.
- **pubblica.py + sentinella**: gli stessi passi del vecchio, ma in un file solo (raccolta → controlli → TPI →
  previsione → sito → verifica → git). Regole A1-A15 di SPEC_PUBBLICAZIONE, Telegram con urllib (libreria standard),
  attività pianificata di Windows come oggi. Si porta per ultima. Motivo: F21, C29.

## 7. Struttura del codice
```
football-scout-index/
  SPEC.md  PIANO.md  README.md
  fsi/
    config.py        pesi, soglie, percorsi (C3)
    db.py            schema SQLite + la sola funzione che legge le righe di una stagione (C2)
    ponte.py         MySQL vecchio -> SQLite (sola lettura; si cancella al cambio)
    raccolta.py      Understat, heXI, Transfermarkt -> SQLite
    controlli.py     regole D2-D13
    tpi.py           TPI (da indice3)
    previsione.py    modello, rivali, prova, forbice, motivi
    sito.py          JSON + HTML nelle due lingue
    pubblica.py      giro completo + sentinella + Telegram
  sito/              modelli HTML, testi.json, un JS, un CSS
  worker/            assistente (JavaScript, Cloudflare)
  tests/             test_c01_... test_c29_..., fixtures/
  uscita/            (fuori da git) pagine generate fino al cambio
```

## 8. Test
- `python -m pytest` dalla cartella. Un file per gruppo di criteri, **il criterio nel nome** (`test_c06_449_minuti_
  niente_previsione`). Più un `test_tracciabilita.py` che controlla che ogni C1-C29 abbia almeno un test (come nel
  motore vecchio).
- Per il Worker: `node --test` (libreria standard di Node).
- Prima i test rossi, poi il codice; alla fine "rompo una regola e il test se ne accorge" per i criteri chiave.

| Criterio | Test (file) | Fase |
|---|---|---|
| C1-C3c | test_tpi.py | 1 |
| C4-C16 | test_previsione.py | 2 |
| C17-C20 | test_sito.py | 3 |
| C21-C24 | test_assistente.py + worker/test | 4 |
| C25-C27 | test_dati.py | 5 |
| C28-C29 | test_pubblica.py | 6 |

## 9. Fasi
- [x] **0. Scheletro** (22/11): repository git, schema SQLite, ponte dal MySQL, fixtures (grezzi 2025-26, rivali, cache).
- [x] **1. TPI** (C1-C3b) 22/11: uguale alla fotografia (scarto ≤ 0,0009 anche sui 5 contesti); regola dei contesti in SPEC_CONTESTI.md; domande Q-C1, Q-C2 aperte.
- [x] **2. Previsione prototipo** (C4-C16) 22/11, 18 test. Verdetto in `prove/prototipo_2024-25_2025-26.json`
      (prova a gruppi, una coppia: PROTOTIPO, NON VERIFICATO):
      - output: Serie A **batte** l'output grezzo di un soffio (ρ 0,737 contro 0,705, intervallo 0,001…0,066);
        Premier **no** per un pelo (0,790 contro 0,758, intervallo −0,000…0,067). Batte minuti, TPI e TPI Pro ovunque
        (Premier: TPI 0,37, TPI Pro 0,33). Forbice ok (copre 77-78%).
      - sottovalutati (crescita): Premier **batte** la regressione verso la media, Serie A no.
      - costruzione (buildup): **non batte** il grezzo in nessuna lega → non si mostra.
      - contesti: **scartati** dal modello (con 0,761, senza 0,763): "contro le big" non aiuta a prevedere.
      - aggiornata: batte il grezzo presto (giornata 5: SA 0,63 contro 0,46; PL 0,70 contro 0,55), poi il margine sparisce
        (Serie A non passa da giornata 10 in poi; Premier passa a 10, 15, 19, 30, non a 25).
- [ ] **3. Sito** (C17-C20) in `uscita/`, te lo apro in locale.
- [ ] **4. Assistente** (C21-C24).
- [ ] **5. Controlli e raccolta** (C25-C27) sulle partite salvate.
- [ ] **6. Pubblicazione** (C28-C29), spenta fino al cambio.
- [ ] **7. Quando Understat torna**: raccolta dal vivo, scarico 2023-24, prova vera, Juventus-Parma reimportata,
      confronto finale (F24) → **tuo via libera** → cambio.

## 9b. Trovato nella fase 0 (22/11, misurato con il ponte)
- **Ruoli**: la regola vera (SPEC_INDICE C5) usa le posizioni Understat partita per partita, che il MySQL **non ha**
  (stavano solo nella cache di soccerdata, ripulita a ogni giro). Il ponte usa il ruolo pubblicato dal motore vecchio
  per chi era in classifica (~350 a stagione) e quello dell'anagrafica per gli altri (54-77 dei giocatori con ≥450'
  per stagione). La raccolta nuova salverà la posizione in ogni riga e la regola si rifarà da lì.
  *(fase 1)* L'anagrafica si usa **solo** per chi aveva troppo pochi minuti per la classifica vecchia: chi aveva i
  minuti e non c'era era stato escluso apposta (es. **Montipò, portiere, che l'anagrafica dà DIF**: entrava fra i
  difensori e spostava la media del ruolo, scarto fino a 0,33). I ruoli si prendono dalla fotografia di fine
  stagione, non dalla più lunga (la giornata 33 aveva 355 giocatori).
- **Infortuni**: la storia c'è solo per Serie A 2025-26 e 2026-27 e Premier 2026-27. **Per la 2024-25 non c'è
  niente**, quindi nella coppia 24-25 → 25-26 l'ingrediente "infortuni" non si può usare. Si recupera solo scaricando
  la storia infortuni per giocatore da Transfermarkt (lavoro in più, da decidere nella fase 2).
- **Età**: manca la data di nascita a 61 giocatori con ≥450' nella 2024-25, per lega (circa il 15%), quasi tutti
  usciti dal campionato dopo quella stagione (quindi pochi entrano nella prova). Per le altre stagioni manca a 0-5.

## 10. Decisioni prese in approvazione
- Q1 → **A**: contesti calcolati, ingrediente candidato, pagina giocatore con numero di partite (SPEC F1b, C3b, C3c).
- Q2 → **repository privata**; home e siti pubblici. Niente copia pubblica del motore.
