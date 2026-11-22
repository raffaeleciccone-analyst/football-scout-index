"""Fase 4 — assistente (SPEC F17-F20, C21-C24): i test veri sono in worker/test (JavaScript, fornitori finti)."""
import shutil
import subprocess
from pathlib import Path

import pytest

WORKER = Path(__file__).parent.parent / "worker"


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js assente")
def test_c21_c24_assistente_numeri_regole_fornitori_tetto():
    r = subprocess.run(["node", "--test"], cwd=WORKER, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
