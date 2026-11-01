"""Build real documents with leanblueprint + this plugin; the control document (the clean one with the declaration
of n removed) must be caught at every use of n, the clean one must pass, and links must point at the declaring item."""
import json
import re
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


PROOF_DOC = r"""\documentclass{report}
\usepackage{amsmath, amsthm}
\usepackage[thms=definition+lemma+theorem+conjecture]{blueprint}
\usepackage[status=status.json]{symbols}
\theoremstyle{definition}
\newtheorem{definition}{Definition}[chapter]
\newtheorem{lemma}[definition]{Lemma}
\newtheorem{theorem}[definition]{Theorem}
\newtheorem{conjecture}[definition]{Conjecture}
\begin{document}
\chapter{C}
\begin{definition}\label{def:a}\defines[X.a]{a}{real number} Let $a=1$.\end{definition}
\begin{theorem}\label{thm:lean}\uses{def:a}\lean{X.ok} $a>0$.\end{theorem}
\begin{lemma}\label{lem:paper}\uses{def:a} $a\ge0$.\end{lemma}
\begin{proof} Since $a=1$.\end{proof}
\begin{lemma}\label{lem:stated}\uses{def:a}\lean{X.stated} $a\ne0$.\end{lemma}
\begin{lemma}\label{lem:bare}\uses{def:a} $a<2$.\end{lemma}
\begin{conjecture}\label{conj:c}\uses{def:a} $a<3$.\end{conjecture}
\begin{theorem}\label{thm:big}\uses{def:a}\contains{lem:paper, lem:bare} $a=1$.\end{theorem}
\end{document}
"""


@pytest.mark.slow
def test_proof_chips(tmp_path):
    """Each statement's heading says what its proof is: verified in Lean (by the status file, not by the Lean name
    alone), proof on paper, no proof yet; a conjecture says open. The JSON export carries the same."""
    (tmp_path / "p.tex").write_text(PROOF_DOC)
    (tmp_path / "status.json").write_text(json.dumps({"X.ok": "verified", "X.stated": {"status": "stated"}}))
    env = dict(os.environ, PATH=f"{BIN}:{os.environ['PATH']}")
    r = subprocess.run([str(BIN / "plastex"), "--plugins", "leanblueprint", "leanblueprint_symbols", "--", "p.tex"],
                       cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "template error" not in r.stdout + r.stderr
    proof = {i["label"]: i["proof"] for i in json.loads((tmp_path / "blueprint-data.json").read_text())["items"]}
    assert proof["thm:lean"] == "verified" and proof["lem:paper"] == "paper"
    assert proof["lem:stated"] == "none" and proof["lem:bare"] == "none" and proof["conj:c"] == "open"
    assert proof["def:a"] is None
    items = {i["label"]: i for i in json.loads((tmp_path / "blueprint-data.json").read_text())["items"]}
    assert items["thm:lean"]["number"] == "1.2" and items["thm:lean"]["tex"] == "$a>0$."
    assert items["def:a"]["tex"] == "Let $a=1$."   # \defines (with its Lean name) and \label removed from the text
    syms = json.loads((tmp_path / "blueprint-data.json").read_text())["symbols"]
    assert {"sym": "a", "type": "real number", "label": "def:a", "lean": "X.a"} in syms
    assert items["thm:lean"]["where"] == {"chapter": "1 C"}
    assert items["thm:big"]["contains"] == ["lem:paper", "lem:bare"] and items["thm:big"]["tex"] == "$a=1$."
    html = (tmp_path / "p" / "sect0001.html").read_text()
    for cls, words in (("verified", "verified in Lean"), ("paper", "proof on paper"), ("none", "no proof yet"),
                       ("open", "open")):
        assert f'proofchip-{cls}">{words}<' in html, cls


def _build(tmp_path, tex, status=None, name="p"):
    (tmp_path / f"{name}.tex").write_text(tex)
    if status is not None:
        (tmp_path / "status.json").write_text(json.dumps(status))
    env = dict(os.environ, PATH=f"{BIN}:{os.environ['PATH']}")
    r = subprocess.run([str(BIN / "plastex"), "--plugins", "leanblueprint", "leanblueprint_symbols", "--", f"{name}.tex"],
                       cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    return {i["label"]: i for i in json.loads((tmp_path / "blueprint-data.json").read_text())["items"]}


@pytest.mark.slow
def test_approve_markers_and_card_hash(tmp_path):
    """Option approve: each labelled card carries a marker with its label and hash; the hash covers the card's proof,
    so editing only the proof changes it, and a card that did not change keeps its hash."""
    tex = PROOF_DOC.replace(r"\usepackage[status=status.json]{symbols}", r"\usepackage[status=status.json,approve]{symbols}")
    (tmp_path / "a").mkdir()
    a = _build(tmp_path / "a", tex, {"X.ok": "verified"})
    html = (tmp_path / "a" / "p" / "sect0001.html").read_text()
    assert f'data-label="lem:paper" data-sha="{a["lem:paper"]["sha"]}"' in html
    assert html.count('class="sym-approve"') == len([i for i in a.values() if i["sha"]])
    (tmp_path / "b").mkdir()
    b = _build(tmp_path / "b", tex.replace("Since $a=1$.", "Because $a=1$."), {"X.ok": "verified"})
    assert b["lem:paper"]["sha"] != a["lem:paper"]["sha"]
    assert b["thm:lean"]["sha"] == a["thm:lean"]["sha"]
    (tmp_path / "c").mkdir()   # a metadata-only edit (a Lean name on \defines) is not a change of the card
    c = _build(tmp_path / "c", tex.replace(r"\defines[X.a]{a}", r"\defines[X.b]{a}"), {"X.ok": "verified"})
    assert c["def:a"]["sha"] == a["def:a"]["sha"]


@pytest.mark.slow
def test_contains_must_name_an_item(tmp_path):
    tex = PROOF_DOC.replace(r"\uses{def:a} $a<3$.", r"\uses{def:a}\contains{lem:nope} $a<3$.")
    _build(tmp_path, tex, {"X.ok": "verified"})
    rep = json.loads((tmp_path / "symbols-report.json").read_text())
    assert any(p["kind"] == "contains" and "lem:nope" in p["detail"] for p in rep)


@pytest.mark.slow
def test_subscripted_use_of_a_plain_symbol_links(tmp_path):
    """sigma declared plain, sigma_e used: the checker accepts it, so it must link (it did not, 2026-11-01)."""
    tex = PROOF_DOC.replace(r"Let $a=1$.", r"Let $a=1$ and $a_e=2$.")
    _build(tmp_path, tex, {"X.ok": "verified"})
    html = (tmp_path / "p" / "sect0001.html").read_text()
    assert re.search(r"\\href\{sect0001\.html#def:a\}\{a_e\}", html), "a_e not linked to def:a"


@pytest.mark.slow
def test_a_named_definition_must_introduce_its_name(tmp_path):
    tex = PROOF_DOC.replace(r"\begin{definition}\label{def:a}", r"\begin{definition}[the constant]\label{def:a}")
    _build(tmp_path, tex, {"X.ok": "verified"})
    rep = json.loads((tmp_path / "symbols-report.json").read_text())
    assert any(p["kind"] == "unnamed" and p["label"] == "def:a" for p in rep)
    (tmp_path / "b").mkdir()
    _build(tmp_path / "b", tex.replace("Let $a=1$.", r"The \defterm{constant} is $a=1$."), {"X.ok": "verified"})
    rep = json.loads((tmp_path / "b" / "symbols-report.json").read_text())
    assert not any(p["kind"] == "unnamed" for p in rep)
