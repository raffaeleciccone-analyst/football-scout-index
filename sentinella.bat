@echo off
rem Sentinella di Football Scout Index. NON registrata come attivita pianificata fino al cambio (SPEC F24):
rem finche gira quella del motore vecchio, questa si lancia a mano (con --stato non scrive e non manda niente).
cd /d "%~dp0"
python -m fsi.pubblica %*
