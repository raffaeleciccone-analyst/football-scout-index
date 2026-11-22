# SPEC — Football Scout Index

Stato: **APPROVATA il 22/11/2026** (intervista 22/11/2026, 13 domande)
Le voci segnate ✱ erano **proposte mie** (di Claude): approvate dall'utente con il resto.

## Problema
Il progetto di oggi (football-index-engine) ha due strumenti cresciuti intrecciati:
- il **TPI** descrive bene la stagione (decili ρ 0,976, si stabilizza dalla giornata 25, riproducibile),
- il **TPI Pro** doveva prevedere ma non ci riesce: verifica "la stagione dopo" (V23) Serie A ρ 0,55,
  Premier 0,36, contro l'output grezzo (gol senza rigori + xA per 90) 0,72 / 0,76.
Il codice è difficile da controllare (parte1_analisi.py > 3.800 righe, TPI e Pro nello stesso main(),
pesi sparsi, regole non dichiarate, frasi scritte fisse, stagioni mescolate nelle query).
Si riscrive **tutto da zero**, pulito, in una repository nuova.

## Uso principale
- U1. **Vetrina per i colloqui**: un selezionatore apre il sito e vede un metodo onesto:
  cosa descrivo, cosa prevedo, e la prova che la previsione batte la statistica semplice (o che non la batte).
  Conta il rigore più del numero.
- U2. **Scouting**: uno scout cerca giocatori **sottovalutati**, cioè **forti ma poco considerati**: la previsione
  dice che renderanno bene, ma oggi giocano poco. *(precisato il 22/11 dopo la prova vera: prima era "faranno
  meglio dei loro numeri di oggi", che misura solo il ritorno verso la media.)*

## Cosa fa

### Descrivere (TPI)
- F1. **TPI descrittivo** come oggi (regole di SPEC_INDICE, collaudata da 3 ricostruzioni alla cieca):
  sulla fotografia 2025-26 ridà gli stessi numeri. Si aggiorna a ogni giornata.
- F1b. **I 5 contesti** (totale, casa, trasferta, contro le prime 6, contro le difese più forti), con la regola
  scritta per intero (oggi SPEC_INDICE C13 è ambigua in almeno quattro punti) e verificata sui numeri di oggi.
  Si usano in due modi (domanda Q1-bis del piano, risposta A):
  - **ingrediente candidato** della previsione ("contro le big", differenza casa/trasferta): il modello lo tiene
    solo se aiuta a prevedere, e il metodo dice il risultato in tutti e due i casi;
  - **descrizione nella pagina giocatore**, sempre con il numero di partite accanto e la scritta "campione
    piccolo" sotto una soglia.

### Prevedere
- F2. **Previsione del rendimento per 90 della stagione dopo** (obiettivo principale): gol senza rigori + xA
  ogni 90 minuti. Esempio: oggi 0,40 → "l'anno prossimo 0,45". Ingredienti grezzi (output per 90, età, minuti,
  tendenza, infortuni...), **pesi stimati dai dati**, mai scelti a mano.
- F3. **Sottovalutati** (la lettura per lo scout, decisione del 22/11): fra chi ha giocato **poco** (da 450' a
  meno di 1500' ✱ nella stagione di partenza) ed è **giovane** (fino a 25 anni ✱ a fine stagione; età
  sconosciuta = fuori, e lo si dice), i giocatori con il **rendimento previsto più alto** (F2), per ruolo.
  *(Limite d'età deciso il 22/11: senza, in cima finivano Dybala e Pedro, che giocano poco per età, non perché
  nessuno li conosca.)* Viene da F2, non è un secondo modello.
- F3b. **Sfortunati sotto porta** (solo descrizione, mai previsione): chi ha avuto molti più xG che gol (xG senza
  rigori − gol senza rigori, per 90). La pagina lo dice: "descrizione della stagione, non una previsione".
  *(Il 22/11 si è misurato che la vecchia lista "crescita prevista" coincideva con questa idea e non batteva la
  regressione verso la media: per questo diventa una descrizione.)*
- F4. **Previsione della costruzione** per difensori e centrocampisti: xG buildup per 90 della stagione dopo
  (e la sua crescita).
- F5. **Classifiche per ruolo**: un giocatore si confronta solo con quelli del suo ruolo.
- F6. **Forbice di incertezza**: ogni previsione ha un intervallo ("circa 0,40, tra 0,20 e 0,60"). Chi ha giocato
  poco ha la forbice più larga ed è avvicinato di più alla media del ruolo.
- F7. **Chi entra**: almeno **450 minuti** nella stagione di partenza, in Serie A o Premier. Gli altri non hanno
  previsione e la pagina scrive il motivo: "storia insufficiente" / "nessun dato nel campionato".
- F8. **Prova onesta con i rivali**: su una stagione mai usata per stimare i pesi, il modello si confronta con
  output grezzo, minuti, TPI e **vecchio TPI Pro** (non più pubblicato come strumento). Il metodo racconta
  la storia: "il TPI Pro non prevedeva (0,55 contro 0,72): misurato e sostituito".
- F9. **Regola dura**: una previsione (F2, F3, F4, forbice, ogni giornata di F10) si mostra **solo se ha passato
  la sua prova**; altrimenti la pagina dice che non l'ha passata. Chi sono i rivali e cosa vuol dire "batte"
  è nei criteri C8-C11.
- F10. **Quando si aggiorna**:
  - **previsione di agosto**: calcolata a fine stagione, **ferma** tutto l'anno; il sito mostra *previsto contro
    reale* giornata per giornata;
  - **previsione aggiornata**: stesso modello con in più la stagione in corso fino a quella giornata; compare
    solo dalle giornate in cui ha passato la prova, prima la pagina scrive "troppo presto per aggiornare";
  - **gennaio** (giornata 19) è un punto fisso, con la sua prova dichiarata nel metodo.

### Il sito
- F11. **Una home comune** a un indirizzo suo (`.../football-scout-index/`) da cui si entra nei **due siti**
  (Serie A, Premier League), che restano separati ai loro indirizzi di oggi.
- F12. In ogni sito, ridisegnate da zero: classifica TPI per ruolo · previsione (forbice + sottovalutati) ·
  pagina giocatore · metodo con la prova onesta.
- F13. **Una sola pagina giocatore**: si sceglie il giocatore (ricerca o clic dalle liste) e si vedono TPI e
  dimensioni, previsione con forbice, i **motivi** della previsione (i 2-3 ingredienti che la spostano di più,
  es. "giovane, pochi minuti, tiri in crescita"), l'andamento partita per partita.
- F14. Il metodo dice chiaramente cosa **non** è misurato: lavoro difensivo puro assente nella fonte;
  xG buildup cresce con il possesso della squadra.
- F15. **Due lingue**: ogni pagina in italiano e in inglese, pulsante IT/EN; nessun testo in una lingua sola.
- F16. **Nessun numero scritto a mano** nelle pagine: ogni numero e ogni frase con numeri nasce dai dati e
  dalle regole (oggi c'erano frasi fisse sbagliate).

### L'assistente
- F17. **Chat nel sito** che risponde su TPI e previsione ("i sottovalutati tra i centrocampisti under 23?"),
  nella lingua della domanda. La chiave API resta nascosta lato server; tetto giornaliero di domande.
- F18. **Non legato a un fornitore**: Claude, OpenAI, Gemini, modelli locali... cambiare = un'impostazione.
- F19. **Cosa può dire**: ogni numero solo dai dati del sito; conoscenza generale solo come contesto, senza
  numeri e segnata "non verificata"; niente notizie (rinnovi, mercato, infortuni di oggi). ✱ (il confine)
- F20. ✱ Vede **tutti** i giocatori con previsione, non solo i primi 100 (si manda solo ciò che serve alla domanda).

### Il giro completo
- F21. **Tutto nuovo**: raccolta (Understat + le altre fonti che servono a TPI e previsione) → controllo dei dati
  (regole di SPEC_DATI) → calcolo → pagine → pubblicazione automatica con sentinella e avvisi Telegram
  (regole di SPEC_PUBBLICAZIONE). Alla fine il motore vecchio si spegne del tutto.
- F22. ✱ **Database proprio**: il nuovo scrive solo nel suo; i database di oggi li legge soltanto, per confrontarsi.
- F23. ✱ **Ordine del lavoro**: prima calcolo e pagine sui dati che ci sono; la raccolta si costruisce sulle
  risposte di Understat salvate sul PC (170 partite in ~/soccerdata) e si prova dal vivo quando Understat torna.
- F24. **Il cambio**: il vecchio si spegne solo quando il nuovo (a) ridà lo stesso TPI, (b) raccoglie le stesse
  partite con gli stessi numeri del DB di oggi, (c) passa tutti i controlli, (d) l'utente dà il via libera.

## Cosa NON fa
- N1. Niente fantacalcio (voti, bonus).
- N2. Non misura il lavoro difensivo puro (contrasti, intercetti, recuperi): la fonte non li ha.
- N3. Non rifà caso-mercato, dashboard Pro, il prototipo dashboard_nuova, le 20 pagine squadra.
- N4. ✱ Non prevede oltre la stagione successiva (niente "tra 3 anni").
- N5. L'assistente non dà notizie e non inventa numeri.

## Criteri di controllo
Ogni criterio diventa almeno un test. ✱ = soglie proposte da me.

**TPI**
- C1. Dai grezzi 2025-26 (tests/fixtures) il TPI dei 354 qualificati è uguale alla fotografia: 354/354 stessi
  giocatori, stesso valore (scarto ≤ 0,01), Spearman 1,000. Valgono anche tutti i criteri di SPEC_INDICE.
- C2. **Stagioni mai mescolate**: aggiungo una partita finta della 2026-27 → TPI e previsione della 2025-26 non cambiano.
- C3b. **Contesti**: dai grezzi 2025-26 totale, casa, trasferta e prime 6 sono uguali al motore di oggi
  (payload 2025-26, campo `ctx`: stesse partite, scarto ≤ 0,01) per chi ha almeno 4 presenze nel contesto.
  *Cambiati apposta il 22/11 (Q-C1 = B, Q-C2 = B, vedi SPEC_CONTESTI):* le difese forti si scelgono sempre dagli
  xG concessi Understat (Serie A 2025-26: Inter, Juventus, Como, Napoli, Roma, Milan; con la settima se la sua
  squadra è fra queste); sotto le 4 presenze un contesto non ha TPI e non entra nella media del ruolo.
- C3c. Nella pagina giocatore ogni contesto mostra il numero di partite; sotto le 8 partite ✱ compare
  "campione piccolo". Il metodo riporta se gli ingredienti di contesto sono stati tenuti o scartati dal modello.
- C3. **Ogni peso e soglia in un posto solo**: cambio un peso lì → cambiano calcolo e pagina del metodo; nessun
  altro file contiene quel numero.

**Previsione**
- C4. **Niente sbirciate nel futuro**: modifico i dati della stagione da prevedere → la previsione non cambia.
  Per la previsione aggiornata alla giornata k: modifico le giornate dopo k → non cambia.
- C5. **Pesi stimati, prova su stagione mai vista**: i pesi si stimano su stagioni di addestramento; la prova usa
  una stagione che non è entrata nella stima (test: tolgo la stagione di prova dai dati → pesi identici).
- C6. Giocatore con 449' → nessuna previsione, motivo "storia insufficiente"; con 450' → previsione.
  Giocatore senza partite in Serie A/Premier nella stagione di partenza → "nessun dato nel campionato".
- C7. Due giocatori con lo stesso output per 90, uno con 500' e uno con 2.500' → il primo ha la forbice più
  larga e la previsione più vicina alla media del ruolo.
- C8. ✱ **"Batte"** vuol dire: sugli stessi giocatori, la correlazione (ρ di Spearman) fra previsione e rendimento
  reale supera quella del rivale, e l'intervallo bootstrap al 90% della differenza sta tutto sopra zero.
- C9. **F2 e F4**: rivale = il dato grezzo della stagione prima (output per 90 / buildup per 90). Se un modello
  finto che copia il grezzo viene messo alla prova → "non batte", e la pagina mostra il grezzo con quella scritta.
- C10. **F3 (sottovalutati)**: la prova si fa **solo sul gruppo** dei giovani con pochi minuti (450'-1499', fino a
  25 anni): lì la previsione deve battere l'output grezzo (come C8). Se non batte → la lista non si mostra e la
  pagina dice perché. Un giocatore con 1500', o con 26 anni, o senza età nota non entra mai nella lista.
- C10b. **F3b**: la lista è ordinata per (xG senza rigori − gol senza rigori) per 90, solo chi ha i 450'; ogni
  pagina che la mostra ha la scritta "descrizione, non previsione".
- C11. ✱ **Forbice all'80%**: sulla stagione di prova, fra il 70% e il 90% dei giocatori finisce dentro la sua
  forbice; altrimenti la forbice non si mostra.
- C12. La pagina del metodo mostra, sugli stessi giocatori e stessa stagione: modello, output grezzo, minuti,
  TPI, TPI Pro, con ρ e intervallo.
- C13. *(22/11)* La prova vera è **a finestra mobile**: ogni stagione di prova si prevede con un modello stimato
  solo sulle coppie che vengono prima (oggi: Premier 3 stagioni di prova, Serie A 2, con le stagioni dell'archivio).
  **Finché c'è una sola coppia di stagioni** (2024-25 → 2025-26) ogni previsione è marcata "prototipo,
  non verificato"; la parola "verificata" compare solo con una prova su una stagione mai vista.
- C14. **Agosto ferma**: rigiro il calcolo alla giornata 12 → la previsione di agosto è identica.
  Giornata la cui prova non è passata → "troppo presto per aggiornare"; giornata 19 → prova dichiarata nel metodo.
- C15. **Motivi**: i motivi mostrati sono gli ingredienti con il contributo maggiore a quella previsione
  (test: azzero l'ingrediente indicato come primo motivo → è quello che sposta di più la previsione).
- C16. **Classifiche per ruolo**: nessun difensore compare nella classifica degli attaccanti; le posizioni sono
  calcolate dentro il ruolo.

**Sito**
- C17. Ogni testo ha versione IT e EN; il pulsante cambia tutta la pagina; un testo senza traduzione fa fallire un test.
- C18. Cambio un dato → cambiano i numeri e le frasi che lo citano (nessun numero fisso nelle pagine).
- C19. Cerco "Lautaro" → si apre la sua scheda; giocatore sotto i 450' → la scheda c'è, con il motivo al posto
  della previsione.
- C20. La home porta ai due siti; ogni sito ha le 4 sezioni di F12; il metodo contiene le frasi di F14.

**Assistente**
- C21. ✱ Su 30 domande di prova (IT e EN), ogni numero nelle risposte esiste nei dati del sito.
- C22. Domanda di notizie ("Yildiz rinnova?") → "non è nei miei dati"; giocatore fuori dai nostri campionati →
  contesto senza numeri, segnato "non verificato".
- C23. Cambio fornitore nell'impostazione (anche un fornitore finto di prova) → l'assistente risponde senza
  toccare il codice.
- C24. La chiave API non compare in nessun file del sito né del repository; oltre il tetto giornaliero → messaggio
  "limite raggiunto", nessuna chiamata al modello.

**Dati, raccolta, pubblicazione**
- C25. Valgono le regole D1-D13 di SPEC_DATI: un difetto ferma la pubblicazione (test: una squadra tutta a xG zero
  in una partita, come Juventus-Parma 2026-27 → stop al passo dati).
- C26. Sulle 170 partite di Understat salvate, la raccolta nuova produce le stesse righe del DB di oggi
  (minuti, gol, assist, tiri, xG, xA, npxG, buildup, chain).
- C27. Il nuovo non scrive mai nei database vecchi (test: ci lavora con un utente in sola lettura e non fallisce).
- C28. Fino al cambio, nessun file viene scritto nelle cartelle serie-a-index e premier-league-index.
- C29. Valgono le regole A1-A15 di SPEC_PUBBLICAZIONE (sentinella, manutenzione Understat, un solo messaggio
  Telegram per blocco + promemoria ogni 7 giorni).

## Vincoli
- V1. Lavoro by spec: intervista → SPEC → approvazione → PIANO → test → codice.
- V2. Codice minimo con le regole di **ponytail** (github.com/DietrichGebert/ponytail, letta il 22/11):
  prima chiedersi se serve, poi se c'è già, poi libreria standard, poi dipendenza installata, poi il minimo;
  niente astrazioni "per dopo"; ogni logica non banale lascia un test; scorciatoie dichiarate con
  `shortcut: <limite>, <quando migliorare>`; mai tagliare validazione, gestione errori, sicurezza.
- V3. Repository nuova. Il motore vecchio resta online fino al cambio (F24).
- V4. Nei commit niente righe di attribuzione a Claude.
- V5. Non pubblicare niente sui siti senza chiedere.
- V6. Dati: MySQL locale serie_a_25_26 e premier_25_26 (2024-25 e 2025-26 complete, 2026-27 in corso).
  Understat in manutenzione dal 5/11: la 2023-24 (serve per la prova vera) si scarica quando torna.
- V7. Base di partenza: SPEC_INDICE, SPEC_PRO, SPEC_DATI, SPEC_VALIDAZIONE, SPEC_PUBBLICAZIONE del motore vecchio
  (C:\dev\football-index-engine); C:\dev\_ricostruzione\indice3\indice.py come esempio di TPI in un file solo.
- V8. Fino al cambio il nuovo scrive le pagine solo in una cartella sua (la sentinella vecchia fa git add -A nei siti).

## Dati disponibili (controllati nel DB il 22/11)
Per partita e giocatore: minuti, gol, assist, tiri, xG, xA, npxG, npG, gialli, rossi, **xG chain**, **xG buildup**.
Mancano contrasti, intercetti, recuperi, duelli. xG buildup = valore delle azioni a cui il giocatore ha partecipato
*senza* tiro e ultimo passaggio: misura la costruzione. Limite: cresce con il possesso della squadra.
Altre fonti usate oggi: heXI (rose, ruoli, xG concessi), Transfermarkt (infortuni, età, contratti, valore di mercato).

## Domande aperte
- ~~D1. Nome~~ → deciso: **Football Scout Index**, repository e cartella `football-scout-index`
  (evitato "Football Index" da solo: piattaforma di scommesse fallita nel 2021).
- D2. (PIANO) TPI Pro come rivale: rifarlo nel codice nuovo da SPEC_PRO o usare i numeri del motore vecchio?
  Per la prova sulla 2023-24 i suoi numeri oggi non esistono.
- ~~D3. Posto della home~~ → deciso: **indirizzo suo**, `raffaeleciccone-analyst.github.io/football-scout-index/`;
  i due siti restano ai loro indirizzi; il portfolio ci punta con un link.
- D4. ✱ La pagina "validazione" di oggi (23 verifiche): propongo che restino nel metodo le verifiche sul TPI
  descrittivo (V1-V22, ricalcolate dal codice nuovo) e che la V23 diventi la prova del nuovo modello (C8-C13).
- D5. Valore di mercato (Transfermarkt): ingrediente o rivale della previsione? Oggi esiste solo il file di fine
  stagione, quindi va usato solo quello della stagione *prima* (C4). Si decide nel PIANO guardando i dati.
- D6. La prova vera arriva con la 2023-24 (C13): finché Understat è giù, il sito nuovo resta "prototipo".
