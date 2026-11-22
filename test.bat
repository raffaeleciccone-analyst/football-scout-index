@echo off
rem Lancia tutti i test e mostra il risultato di ognuno (il nome del test contiene il criterio della SPEC).
chcp 65001 >nul
cd /d "%~dp0"
echo Test di Football Scout Index - ci vogliono circa 3 minuti.
echo.
python -m pytest -v --color=yes tests
echo.
pause
