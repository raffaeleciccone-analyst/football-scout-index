"""Tutti i percorsi, le leghe e (dalla fase 1) i pesi e le soglie: un posto solo (SPEC C3)."""
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DB = RADICE / "dati" / "fsi.sqlite"
USCITA = RADICE / "uscita"

# lega -> database MySQL del motore vecchio (letto soltanto: SPEC F22, C27)
LEGHE = {"serie_a": "serie_a_25_26", "premier": "premier_25_26"}
