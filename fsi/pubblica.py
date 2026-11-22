"""Pubblicazione automatica (SPEC F21, F24, C28-C29: regole A1-A15 di SPEC_PUBBLICAZIONE del motore vecchio).

Ogni mattina la sentinella guarda il calendario: quando una giornata è chiusa per tutte le squadre fa il giro
(raccolta -> dati -> archivio -> calcolo -> sito -> verifica -> online) e lo scrive su Telegram.
Fino al cambio (F24) DESTINAZIONE_SITI è vuota: il giro si ferma prima di andare online e non tocca i siti.
Uso: python -m fsi.pubblica [--stato]
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from fsi import config as C

GIORNATA_DEBUTTO = 3          # A4: una stagione nuova si pubblica dalla giornata 3
GIORNI_FERMO_AVVISO = 10      # A14
GIORNI_PROMEMORIA = 7         # A15


# ---- A1-A3: calendario, fonte, stagione ----
def giornate_chiuse(cal: pd.DataFrame) -> int:
    """A1: quante giornate sono state giocate da tutte le squadre. Un calendario vuoto è un errore (A2)."""
    if cal.empty:
        raise ValueError("calendario vuoto: è un errore, non 'zero giornate'")
    squadre = set(cal["casa"]) | set(cal["trasferta"])
    n = 0
    for _, g in cal.groupby("giornata"):
        giocate = g[g["giocata"]]
        if set(giocate["casa"]) | set(giocate["trasferta"]) == squadre:
            n += 1
    return n


def stato_fonte(testo: str) -> str:
    """A2: la manutenzione di Understat si dice in chiaro; una pagina vuota o rotta è un errore, non manutenzione."""
    if "come back soon" in testo.lower():
        return "manutenzione"
    return "ok" if testo.strip() else "errore"


def stagione_da_data(giorno: dt.date) -> str:
    """A3: dalla data, non dalla stagione pubblicata. Da luglio comincia la stagione nuova."""
    a = giorno.year if giorno.month >= 7 else giorno.year - 1
    return f"{a}-{str(a + 1)[2:]}"


# ---- A4-A7: quando si fa il giro; lo stato, una lega per volta ----
def decidi(stato: dict, chiuse: int, oggi: dt.date) -> dict:
    pubblicata = stato.get("pubblicata", 0)
    if pubblicata == 0 and chiuse < GIORNATA_DEBUTTO:
        return {"azione": "attendi", "perche": f"debutto dalla giornata {GIORNATA_DEBUTTO}"}
    if chiuse <= pubblicata:
        return {"azione": "attendi", "perche": "nessuna giornata nuova"}
    f = stato.get("fallito")
    if f and f["giornata"] == chiuse and f["giorno"] == oggi.isoformat():
        return {"azione": "attendi", "perche": "già provato oggi: si riprova domani"}
    return {"azione": "giro", "giornata": chiuse}


def leggi_stato(percorso) -> dict:
    try:
        return json.loads(Path(percorso).read_text(encoding="utf-8"))
    except (OSError, ValueError):   # A6: uno stato illeggibile non ferma niente
        return {}


def scrivi_stato(percorso, stato):
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    Path(percorso).write_text(json.dumps(stato, indent=1, ensure_ascii=False), encoding="utf-8")


# ---- A13-A15: Telegram ----
def manda(testo) -> bool:
    """A13: senza bot configurato o con Telegram giù non fallisce niente."""
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if not token or not chat:
        print("[telegram non configurato]", testo)
        return False
    try:
        dati = urllib.parse.urlencode({"chat_id": chat, "text": testo}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", dati, timeout=20)
        return True
    except OSError:
        return False


def messaggio_blocco(stato: dict, motivo, oggi: dt.date):
    """A15: un blocco si annuncia una volta; promemoria ogni 7 giorni; un motivo diverso subito; lo sblocco si dice."""
    b = stato.get("blocco")
    if motivo is None:
        if b:
            del stato["blocco"]
            return f"Football Scout Index: sbloccato (era fermo al passo '{b['motivo']}' dal {b['dal']})."
        return None
    if not b or b["motivo"] != motivo:
        stato["blocco"] = {"motivo": motivo, "dal": oggi.isoformat(), "ultimo": oggi.isoformat()}
        return f"Football Scout Index: pubblicazione ferma al passo '{motivo}'. Il sito resta com'era."
    if (oggi - dt.date.fromisoformat(b["ultimo"])).days >= GIORNI_PROMEMORIA:
        b["ultimo"] = oggi.isoformat()
        return f"Football Scout Index: promemoria, ancora fermo al passo '{motivo}' dal {b['dal']}."
    return None


def avviso_fermo(stato: dict, giorni_fermo: int):
    """A14: dati fermi da 10 giorni o più: un avviso, una volta sola per blocco."""
    if giorni_fermo == 0:
        stato.pop("fermo_avvisato", None)
        return None
    if giorni_fermo >= GIORNI_FERMO_AVVISO and not stato.get("fermo_avvisato"):
        stato["fermo_avvisato"] = True
        return f"Football Scout Index: i dati sono fermi da {giorni_fermo} giorni (Understat in manutenzione?)."
    return None


# ---- A9-A12: archivio, verifica, online ----
def archivia(uscita, archivio, stagione):
    """A9: al cambio di stagione mette al sicuro il sito della stagione finita. Non cancella e non sovrascrive."""
    destinazione = Path(archivio) / stagione
    if not destinazione.exists():
        shutil.copytree(uscita, destinazione)
    return destinazione


def verifica(cartella, stagione) -> list[str]:
    """A10-A11: tutte le pagine dicono la stessa stagione; nessuna pagina ha l'avviso di dati fermi."""
    problemi = []
    for dati_js in Path(cartella).glob("*/dati.js"):
        testo = dati_js.read_text(encoding="utf-8")
        if "giocatori" in testo or '"stagione"' in testo:
            d = json.loads(testo.removeprefix("window.DATI = ").rstrip().rstrip(";"))
            if "stagione" in d and d["stagione"] != stagione:
                problemi.append(f"{dati_js.parent.name}: stagione {d['stagione']} invece di {stagione}")
    for pagina in Path(cartella).rglob("*.html"):
        if 'id="avviso-fonte"' in pagina.read_text(encoding="utf-8"):
            problemi.append(f"{pagina.parent.name}/{pagina.name}: c'è ancora l'avviso di dati fermi")
    return problemi


def puo_andare_online(stato_lega: dict) -> bool:
    """A12: online da sola solo dalla seconda pubblicazione della stagione; la prima si guarda a mano."""
    return stato_lega.get("pubblicazioni", 0) >= 1


# ---- A8: i passi del giro, nell'ordine; il primo che fallisce ferma tutto ----
PASSI = [("raccolta", "scarica le partite della stagione da Understat"),
         ("dati", "le regole dei dati puliti: un difetto ferma la pubblicazione"),
         ("archivio", "al cambio di stagione mette al sicuro il sito della stagione finita"),
         ("calcolo", "controlla che ci sia la previsione di agosto (si scrive una volta)"),
         ("sito", "TPI, previsione, pagine nelle due lingue"),
         ("verifica", "stagione coerente, nessuna pagina rimasta indietro"),
         ("online", "copia nei siti e git push (solo dopo il cambio, con il via libera)")]


def _raccolta(ctx):
    from fsi import db, raccolta
    con = db.apri()
    for lega in C.LEGHE:
        raccolta.scarica(lega, ctx["stagione"])
        raccolta.importa_cartella(con, raccolta.CACHE, lega, ctx["stagione"])
    return True


def _dati(ctx):
    from fsi import controlli, db
    difetti = [e for e in controlli.controlla(db.apri(), ctx["stagione"]) if e["grave"]]
    ctx["difetti"] = difetti
    return not difetti


def _archivio(ctx):
    if ctx.get("stagione_finita"):
        archivia(C.USCITA, C.ARCHIVIO, ctx["stagione_finita"])
    return True


def _calcolo(ctx):
    return True   # il calcolo (TPI, previsione) gira dentro il passo "sito"; la previsione di agosto la scrive lui


def _sito(ctx):
    from fsi import db, sito
    sito.costruisci(db.apri(), ctx["stagione"], ctx["stagione"])
    return True


def _verifica(ctx):
    ctx["problemi"] = verifica(C.USCITA, ctx["stagione"])
    return not ctx["problemi"]


def _online(ctx):
    if not C.DESTINAZIONE_SITI:
        print("online: nessuna destinazione (fino al cambio il sito resta in uscita/)")
        return True
    if not puo_andare_online(ctx.get("stato_lega", {})):
        print("online: prima pubblicazione della stagione, si guarda a mano prima del push")
        return True
    for nome, repo in C.DESTINAZIONE_SITI.items():
        shutil.copytree(C.USCITA / nome, repo, dirs_exist_ok=True)
        for comando in (["git", "add", "-A"], ["git", "commit", "-m", f"Aggiornamento {ctx['stagione']}"], ["git", "push"]):
            r = subprocess.run(comando, cwd=repo, capture_output=True, text=True)
            if r.returncode and comando[1] != "commit":   # "niente da committare" non è un errore
                print(f"online: {' '.join(comando)} fallito in {repo}: {r.stderr.strip()}")
                return False
    return True


FUNZIONI = {"raccolta": _raccolta, "dati": _dati, "archivio": _archivio, "calcolo": _calcolo,
            "sito": _sito, "verifica": _verifica, "online": _online}


def giro(ctx) -> dict:
    for nome, _ in PASSI:
        if not FUNZIONI[nome](ctx):
            return {"ok": False, "passo": nome}
    return {"ok": True}


# ---- la sentinella ----
def _fonti_dal_vivo(stagione):
    """Per lega: stato di Understat e giornate chiuse (dal file della stagione che soccerdata scarica)."""
    from fsi import raccolta
    out = {}
    for lega, (numero, _) in raccolta.CODICE.items():
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    f"https://understat.com/league/{'Serie_A' if lega == 'serie_a' else 'EPL'}/{stagione[:4]}",
                    headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                testo = r.read().decode("utf-8", errors="replace")
        except OSError:
            testo = ""
        fonte = stato_fonte(testo)
        chiuse = None
        if fonte == "ok":
            try:
                raccolta.scarica(lega, stagione)
                partite = json.loads((raccolta.CACHE / f"league_{numero}_season_{stagione[:4]}.json").read_text(encoding="utf-8"))["dates"]
                cal = pd.DataFrame([(0, p["h"]["title"], p["a"]["title"], p["isResult"], p["datetime"]) for p in partite],
                                   columns=["giornata", "casa", "trasferta", "giocata", "data"])
                cal["giornata"] = cal.groupby("casa").cumcount() + 1   # shortcut: come in raccolta.py
                chiuse = giornate_chiuse(cal)
            except (OSError, ValueError, KeyError) as e:
                fonte = f"errore ({e})"
        out[lega] = (fonte, chiuse)
    return out


def sentinella(percorso_stato, solo_stato=False, oggi=None, fonti=None):
    oggi = oggi or dt.date.today()
    stagione = stagione_da_data(oggi)
    fonti = fonti if fonti is not None else _fonti_dal_vivo(stagione)
    stato = {} if solo_stato else leggi_stato(percorso_stato)
    for lega, (fonte, chiuse) in fonti.items():
        s = stato.setdefault(lega, {})
        if fonte != "ok":
            print(f"{lega}: Understat {fonte}")
            if not solo_stato:
                giorni = (oggi - dt.date.fromisoformat(s.setdefault("fermo_dal", oggi.isoformat()))).days
                msg = avviso_fermo(s, giorni)
                if msg:
                    manda(msg)
            continue
        s.pop("fermo_dal", None)
        avviso_fermo(s, 0)
        d = decidi(s, chiuse, oggi)
        print(f"{lega}: {chiuse} giornate chiuse, pubblicata {s.get('pubblicata', 0)} -> {d['azione']} {d.get('perche', '')}")
        if solo_stato or d["azione"] != "giro":
            continue
        esito = giro({"stagione": stagione, "stato_lega": s})
        if esito["ok"]:
            s.update(pubblicata=d["giornata"], pubblicazioni=s.get("pubblicazioni", 0) + 1)
            s.pop("fallito", None)
            for msg in (messaggio_blocco(s, None, oggi), f"Football Scout Index: {lega} aggiornata alla giornata {d['giornata']}."):
                if msg:
                    manda(msg)
        else:
            s["fallito"] = {"giornata": d["giornata"], "giorno": oggi.isoformat()}
            msg = messaggio_blocco(s, esito["passo"], oggi)
            if msg:
                manda(msg)
    if not solo_stato:
        scrivi_stato(percorso_stato, stato)
    return stato


if __name__ == "__main__":
    sentinella(C.STATO_PUBBLICAZIONE, solo_stato="--stato" in sys.argv)
