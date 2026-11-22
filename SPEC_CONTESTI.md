# SPEC_CONTESTI — la regola completa dei 5 contesti (SPEC F1b, C3b)

Stato: **scritta il 22/11/2026**, ricavata da `parte1_analisi.py` del motore vecchio (`compute_dimensions`,
`compute_all_contexts`, `compute_bayesian_priors`, `_weighted_tpi`, `z_series`) e **verificata**: rifatto da qui,
il TPI di ogni contesto torna uguale al payload 2025-26 per tutti i giocatori con almeno 4 presenze nel contesto
(1.731 valori, scarto massimo 0,0009, stesso numero di partite per tutti). Test: `test_c03b_...`.
Chiude i punti che SPEC_INDICE C13 lasciava aperti (trovati dalla ricostruzione alla cieca).

## I contesti
- **totale**: tutte le presenze (almeno 1 minuto).
- **casa** / **trasferta**: le presenze con quel lato.
- **vs_top6**: contro le prime 6 della classifica dei dati (punti, poi differenza reti, poi gol fatti),
  **tolta la sua squadra** (se la sua squadra è fra le prime 6, i contesto ha 5 avversari).
- **vs_forti**: contro le 6 difese che concedono meno xG a partita, **tolta la sua squadra e presa la settima al
  suo posto** (⚠ regola nascosta 1: diversa da vs_top6).
- "La sua squadra" = quella dell'ultima partita giocata nella stagione.

## Da dove vengono le difese (⚠ regola nascosta 2)
- Se c'è il file heXI/Sportmonks degli xG concessi della stagione, vince lui. Oggi esiste **solo per la Serie A
  2025-26**; per le altre stagioni e per la Premier si usano gli xG concessi delle partite Understat.
- Con l'ordine Understat, nella Serie A 2025-26 la sesta difesa è il Milan invece del Bologna, e il TPI
  "contro le difese forti" cambia per 318 giocatori su 335. **Domanda aperta per l'utente (Q-C1).**
- A stagione in corso il file esterno non si usa (sono xG a stagione intera: sarebbe sbirciare nel futuro).

## Le dimensioni in un contesto (giocatore con almeno 4 presenze nel contesto)
- **output** e **buildup** per 90, divisi per la SOS media degli avversari *del contesto*; poi tirati verso la
  media del ruolo *nel contesto* con lo stesso K dell'output del totale (600 × moltiplicatore del giocatore) e i
  minuti del contesto.
- **centralità**: (xG+xA del giocatore + prior × K) / (xG della squadra + K) × 100, con
  - prior = somma xG+xA / somma xG squadra degli ATT e CEN *nel contesto*;
  - K = 12 × (1,8 se invernale) × partite totali / partite del contesto, al massimo 8 volte la base.
- **effetto squadra**: come nel totale, ma "senza di lui" = partite della squadra senza di lui *dello stesso
  contesto* (in casa → in casa; contro le prime 6 → contro le prime 6), almeno 6.
- **consistenza**: come nel totale, sulle presenze del contesto (almeno 6).
- **finalizzazione** e **forma**: quelle del totale, uguali in tutti i contesti.

## z e TPI del contesto
- z dentro il ruolo e dentro il contesto (estremi al 5°-95°, limite ±3); se nel ruolo ci sono **meno di 6 valori**
  del contesto, media e deviazione si prendono dai valori del totale dello stesso ruolo.
- Media pesata con gli stessi pesi del totale, riproporzionati sulle dimensioni presenti.
- Poi gli stessi passaggi del totale: riporto verso la media del ruolo *del contesto* con la confidenza del
  totale → × peso del ruolo → × penalità di disponibilità.
- ⚠ **Regola nascosta 3**: chi ha **meno di 4 presenze** in un contesto riceve lo stesso un TPI di quel contesto,
  fatto solo di finalizzazione e forma (le uniche dimensioni presenti), ed entra nella media del ruolo usata per
  il riporto. Nel sito nuovo i contesti si **mostrano** solo da 4 presenze (C13), ma il calcolo la tiene, per
  ridare gli stessi numeri.

## Domande aperte
- Q-C1. Difese forti: tenere la fonte heXI/Sportmonks (uguale a oggi, ma una fonte in più e solo per una
  stagione) o usare sempre gli xG concessi Understat (una fonte sola, coerente in tutte le stagioni, ma
  "contro le difese forti" cambia per quasi tutti nella Serie A 2025-26)?
- Q-C2. Regola nascosta 3: tenerla (numeri uguali) o toglierla (i contesti sotto 4 presenze non esistono neanche
  nel calcolo, e la media del ruolo cambia un poco)?
