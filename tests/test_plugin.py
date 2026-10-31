"""Build real documents with leanblueprint + this plugin; the control document (the clean one with the declaration
of n removed) must be caught at every use of n, the clean one must pass, and links must point at the declaring item."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"
BIN = Path(sys.executable).parent


def build(tmp_path, name):
    for f in ("clean.tex", "control.tex"):
        shutil.copy(FIX / f, tmp_path / f)
    env = dict(os.environ, PATH=f"{BIN}:{os.environ['PATH']}")
    r = subprocess.run([str(BIN / "plastex"), "--plugins", "leanblueprint", "leanblueprint_symbols", "--",
                        f"{name}.tex"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads((tmp_path / "symbols-report.json").read_text()), tmp_path


@pytest.mark.slow
def test_clean_document_passes(tmp_path):
    problems, out = build(tmp_path, "clean")
    assert problems == []
    html = (out / "clean" / "sect0001.html").read_text()
    assert r"\href{sect0001.html#def:matrix-unit}{M_e}" in html
    data = json.loads((out / "blueprint-data.json").read_text())
    assert {i["label"] for i in data["items"]} >= {"def:wiring", "def:matrix-unit", "lem:box"}


@pytest.mark.slow
def test_control_document_is_caught(tmp_path):
    problems, _ = build(tmp_path, "control")
    n_uses = {p["label"] for p in problems if p["kind"] == "undeclared" and p["detail"].startswith("n ")}
    assert n_uses == {"def:wiring", "def:stub", "def:matrix-unit"}
