# Football Scout Index

**Who will do well next season in Serie A and the Premier League? A forecast that is shown only
where, on seasons it had never seen, it beat the simple statistic.**

**Status:** finished and tested. It replaces the engine behind
[serie-a-index](https://raffaeleciccone-analyst.github.io/serie-a-index/) and
[premier-league-index](https://raffaeleciccone-analyst.github.io/premier-league-index/); the switch happens when
Understat (the data source, in maintenance since 5 November 2026) is back.

## The results

The forecast predicts non-penalty goals + expected assists per 90 minutes for the next season. It is tested on a
rolling window: train on the past, predict a season it has never seen, compare with what really happened.

| League | Forecast | Simple statistic (last season per 90') | Verdict |
|---|---|---|---|
| Premier League | 0.82 | 0.78 | **beats it**: the forecast is shown |
| Serie A | 0.75 | 0.74 | **not yet** (lead too small): the site shows the simple statistic |

Numbers are rank correlations (Spearman), averaged within each season; "beats" means the 5–95% bootstrap interval
of the difference is above zero. The young underrated players list beats the simple statistic in Serie A
(0.74 vs 0.62), not in the Premier League, so it is shown only in Serie A. Things that were tested and did **not**
help (contexts, injuries, build-up) are not used, and the site says so.

**Tools:** Python (pandas, scikit-learn), SQLite, Jinja2, HTML/CSS/JavaScript, a Cloudflare Worker for the
assistant. Data from Understat; injuries from Transfermarkt.

## What is inside

| Part | What it does |
|---|---|
| `fsi/tpi.py` | The TPI: who is doing well **now**, role by role (descriptive, it does not predict) |
| `fsi/previsione.py` | The forecast with its range, the reasons, the rolling-window test |
| `fsi/sito.py`, `sito/` | The static site: one home, one site per league, Italian and English |
| `fsi/pubblica.py` | The watchdog: updates after each matchday, never publishes if a check fails |
| `fsi/controlli.py` | Data checks (missing matches, impossible minutes, duplicates…) |
| `worker/` | "Ask the data": answers only with the site's numbers; every number is checked |

## How it was built

Spec first: [SPEC.md](SPEC.md) says what the program must do and how each rule is checked,
[PIANO.md](PIANO.md) says how, and every rule has a test named after it (`tests/`).

```
python -m pytest            # all the tests
python -m fsi.sito          # build the site into uscita/
```

I used an AI assistant to write the code; the question, the method and the checking of the results are mine.
