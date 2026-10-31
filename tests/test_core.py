"""Positive controls: each defect found by hand in the Hill-class plan (2026-10-31) must be caught, and the
repaired text must pass clean."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leanblueprint_symbols.core import check, tokens  # noqa: E402

WIRING = {"label": "def:wiring", "kind": "definition",
          "defines": [("n", "integer"), ("V", "set"), ("E", "finite set"), ("W", "annotated wiring"),
                      ("s", "map E -> V"), ("t", "map E -> V"), (r"\sigma", "sign map"), (r"\nu", "Hill map"),
                      ("E_j", "edges into j")],
          "binds": ["j"],
          "math": [r"n\ge1", r"V=\{1,\dots,n\}", r"W=(E,s,t,\sigma,\nu)", r"E_j=\{e: t(e)=j\}"],
          "text": "Fix an integer $n\\ge1$ and let $V=\\{1,\\dots,n\\}$."}
MATRIX_UNIT = {"label": "def:matrix-unit", "kind": "definition",
               "defines": [("M_e", r"matrix in $\mathbb R^{n\times n}$")], "binds": ["e", "k", "l"],
               "terms": ["matrix unit"],
               "math": [r"M_e\in\mathbb R^{n\times n}", r"(M_e)_{kl}=1", r"k=t(e)", r"l=s(e)"],
               "text": "For an edge $e$, the matrix unit of $e$ is ..."}


def kinds(problems):
    return sorted((p["kind"], p["label"]) for p in problems)


def test_tokens_keep_whole_symbols():
    assert ("A", True, "") in tokens(r"\det(I-A_{S_J})")
    assert ("h", True, "-") in tokens(r"h^-_{K,\nu}(x)")
    assert ("B", True, r"\mathrm{nd}") in tokens(r"B_k^{\mathrm{nd}}")
    assert (r"\tilde H", True, "") in tokens(r"\prod_e\tilde H_e")
    assert ("x", False, "") in tokens(r"x^2") and ("x", False, "2") not in tokens(r"x^2")
    assert (r"\mathcal E", False, "") in tokens(r"\mathcal E(x)_{ji}")
    assert not [t for t in tokens(r"\mathbb R^{n}") if t[0] == r"\mathbb R"]


def test_clean_passes():
    assert check([WIRING, MATRIX_UNIT]) == []


def test_undefined_n_is_caught():
    w = dict(WIRING, defines=[d for d in WIRING["defines"] if d[0] != "n"])
    found = [p for p in check([w, MATRIX_UNIT]) if p["kind"] == "undeclared" and p["detail"].startswith("n ")]
    assert {p["label"] for p in found} == {"def:wiring", "def:matrix-unit"}


def test_undefined_V_is_caught():
    w = dict(WIRING, defines=[d for d in WIRING["defines"] if d[0] != "V"])
    assert ("undeclared", "def:wiring") in kinds(check([w]))


def test_bound_variable_must_be_declared():
    m = dict(MATRIX_UNIT, binds=["k", "l"])           # "for an edge e" missing
    assert any(p["detail"].startswith("e ") for p in check([WIRING, m]))


def test_overloaded_eta_is_caught():
    elasticity = {"label": "def:elasticity", "kind": "definition", "defines": [(r"\eta_e", "elasticity at x")],
                  "binds": ["e"], "math": [r"\eta_e"], "text": ""}
    box_point = {"label": "lem:multi-affinity", "kind": "lemma", "defines": [(r"\eta_e", "a point of the box")],
                 "binds": ["e"], "math": [r"\eta_e"], "text": ""}
    assert ("redeclared", "lem:multi-affinity") in kinds(check([WIRING, elasticity, box_point]))


def test_untyped_declaration_is_caught():
    m = dict(MATRIX_UNIT, defines=[("M_e", "")])
    assert ("untyped", "def:matrix-unit") in kinds(check([WIRING, m]))


def test_term_before_definition_is_caught():
    early = {"label": "thm:uniqueness", "kind": "theorem", "math": [], "binds": [],
             "text": "Then I - E(x) is a P-matrix."}
    pdef = {"label": "def:pmatrix", "kind": "definition", "terms": ["P-matrix"], "math": [], "text": ""}
    assert ("term-before", "thm:uniqueness") in kinds(check([WIRING, early, pdef]))


def test_gloss_in_definition_is_caught():
    w = dict(WIRING, text=WIRING["text"] + " so that R^n has one coordinate per gene.")
    assert ("gloss", "def:wiring") in kinds(check([w]))


def test_proof_inherits_its_statement_bindings():
    lemma = {"label": "lem:box", "kind": "lemma", "binds": ["x", "e"], "math": [r"M_e x"], "text": ""}
    proof = {"label": "prf:box", "kind": "proof", "parent": "lem:box", "math": [r"M_e x"], "text": ""}
    assert check([WIRING, MATRIX_UNIT, lemma, proof]) == []


def test_binders_inside_a_formula():
    item = {"label": "lem:x", "kind": "lemma", "math": [r"\sum_{e\in E}M_e", r"\{i: i\in V\}", r"\forall j\ E_j"],
            "text": ""}
    assert check([WIRING, MATRIX_UNIT, item]) == []
    stray = dict(item, math=[r"\sum_{e\in E}M_e + q"])   # q is not bound anywhere
    assert any(p["detail"].startswith("q ") for p in check([WIRING, MATRIX_UNIT, stray]))


def test_scan_spans_cover_whole_symbols():
    from leanblueprint_symbols.core import scan
    src = r"\det(I-A_{S_J})+h^-_{K,\nu}(x)"
    spans = {src[a:b] for k, a, b in scan(src)}
    assert "A_{S_J}" in spans and r"h^-_{K,\nu}" in spans


def test_link_wraps_outermost_declared_symbols_only():
    from leanblueprint_symbols.core import link
    table = {("A", True, ""): "#def-corner", ("S", False, ""): "#def-S", ("x", False, ""): None}
    out = link(r"\det(I-A_{S_J}) + x", lambda k: table.get(k))
    assert out == r"\det(I-\href{#def-corner}{A_{S_J}}) + x"


def test_text_and_environment_names_are_not_symbols():
    assert tokens(r"\begin{cases}1 & \text{if } k=t(e)\end{cases}") == [("k", False, ""), ("t", False, ""), ("e", False, "")]


def test_component_of_a_declared_vector():
    item = {"label": "lem:c", "kind": "lemma", "binds": ["x"], "math": [r"x_{s(e)}", r"x_i"], "text": "",
            "defines": []}
    probs = check([WIRING, item])
    assert not [p for p in probs if p["detail"].startswith("x ")]


def test_scripts_after_spaces():
    assert ("\\sigma", True, "") in tokens(r"\sigma _e") and ("A", True, "") in tokens(r"A _{S}")
