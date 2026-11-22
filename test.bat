@echo off
rem Lancia tutti i test in silenzio e apre il rapporto in italiano nel Blocco note.
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo Test di Football Scout Index: circa 3 minuti.
echo Alla fine si apre il rapporto nel Blocco note. Questa finestra si chiude da sola.
python -m pytest -q tests >nul 2>&1
start "" notepad "uscita\rapporto_test.txt"
