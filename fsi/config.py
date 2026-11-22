"""Tutti i percorsi, le leghe, i pesi e le soglie: un posto solo (SPEC C3). La pagina del metodo li legge da qui."""
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DB = RADICE / "dati" / "fsi.sqlite"
USCITA = RADICE / "uscita"

# lega -> database MySQL del motore vecchio (letto soltanto: SPEC F22, C27)
LEGHE = {"serie_a": "serie_a_25_26", "premier": "premier_25_26"}

# ---- TPI (SPEC_INDICE del motore vecchio; i numeri fra parentesi sono i suoi criteri) ----
QUOTA_MINUTI = 0.20                       # C1: soglia = max(20% dei minuti disponibili, 30° percentile)
PERCENTILE_MINUTI = 30
QUOTA_INVERNALI = 0.12                    # C2
FINESTRA_INVERNALE = ("01-01", "02-05")   # C2: 1 gennaio - 5 febbraio, compresi

# C6: pesi delle 7 dimensioni. Sommano a 1,03 (scelta del 21/11: si pubblicano i pesi effettivi);
# il calcolo li riproporziona sempre sulle dimensioni presenti.
PESI_TPI = {"output": 0.32, "buildup": 0.10, "centralita": 0.18, "boost": 0.05,
            "consistenza": 0.07, "finishing": 0.20, "form": 0.11}
PESO_RUOLO = {"ATT": 1.00, "CEN": 0.85, "DIF": 0.55}   # C8

K_OUTPUT = 600.0                          # C9b: minuti di "media del ruolo" aggiunti all'output
MULT_K_MINUTI = (75.0, 2.5)               # riferimento e tetto del moltiplicatore per chi gioca spezzoni
MULT_K_PARTITE = (30.0, 3.0)              # riferimento e tetto per chi gioca poche partite
MULT_K_LIMITI = (1.0, 3.0)
K_CENTRALITA = 12.0                       # C9
FATTORE_K_INVERNALI = 1.8
K_CONTESTO_TETTO = 8.0                    # nei contesti K centralità cresce come partite totali / del contesto, fino a 8x

BOOST_MIN_SENZA = 6                       # C6b: partite della squadra senza di lui
BOOST_K = 8.0
BOOST_PESO_MAX = 10.0
CONSISTENZA_MIN_PRESENZE = 6
ALFA_FORMA = 0.30                         # C11

Z_ESTREMI = (5, 95)                       # C7
Z_LIMITE = 3.0
Z_MIN_VALORI = 3
Z_MIN_RUOLO_CONTESTO = 6                  # sotto, media e deviazione vengono dal contesto totale (C13)

CONF_PERCENTILE_MINUTI = 95               # C10b
CONF_PARTITE = (30.0, 0.3)                # riferimento, minimo
CONF_MINUTI_PARTITA_MIN = 0.4
CONF_MINIMO = 0.35                        # C10: il TPI ne tiene sempre almeno il 35%

DISP_PIENA, DISP_BASSA, DISP_PENALITA = 0.70, 0.30, 0.85   # C12b

# ---- Contesti (SPEC F1b) ----
CONTESTI = ["totale", "casa", "trasferta", "vs_top6", "vs_forti"]
CONTESTO_MIN_PRESENZE = 4                 # C13
N_SQUADRE_FORTI = 6                       # "prime 6" e "difese più forti"

# ---- Previsione (SPEC F2-F10) ----
SOGLIA_PREVISIONE = 450                   # F7: minuti nella stagione di partenza
MINUTI_METRO = 900                        # rendimento reale misurabile solo da 900' nella stagione dopo (come V23)
GRIGLIA_K = [0, 150, 300, 600, 1000, 1500, 2500, 4000]   # minuti di "media del ruolo" provati per il tiraggio
COPERTURA_MIN, COPERTURA_MAX = 0.70, 0.90                 # C11: forbice all'80%
CONTROLLI_AGGIORNATA = [5, 10, 15, 19, 25, 30]            # F10: giornate in cui si prova la previsione aggiornata
