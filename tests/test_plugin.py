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


@pytest.mark.slow
def test_reader_css_and_lean_urls(tmp_path):
    """Options reader, css=URL and a status file with urls: both pages (the text and the dependency graph, which the
    package resources do not reach) link the theme and the stylesheet, and a Lean tag links to the given url instead
    of the mathlib docs."""
    src = (FIX / "clean.tex").read_text()
    src = src.replace(r"\usepackage{symbols}", r"\usepackage[reader,css=/fonts.css,status=status.json]{symbols}")
    src = src.replace(r"\begin{lemma}[the box]\label{lem:box}", r"\begin{lemma}[the box]\label{lem:box}\lean{X.box}")
    assert r"\lean{X.box}" in src
    (tmp_path / "reader.tex").write_text(src)
    (tmp_path / "status.json").write_text(json.dumps({"X.box": {"status": "verified", "url": "/src?path=X.lean&line=3"}}))
    env = dict(os.environ, PATH=f"{BIN}:{os.environ['PATH']}")
    r = subprocess.run([str(BIN / "plastex"), "--plugins", "leanblueprint", "leanblueprint_symbols", "--", "reader.tex"],
                       cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    out = tmp_path / "reader"
    page, graph = (out / "sect0001.html").read_text(), (out / "dep_graph_document.html").read_text()
    for html in (page, graph):
        assert html.count("styles/reader.css") == 1 and html.count('href="/fonts.css"') == 1
    assert "js/reader.js" in page and (out / "js" / "reader.js").exists()
    assert "/src?path=X.lean" in page and "find/#doc/X.box" not in page + graph
