r"""plasTeX package `symbols`: declared, checked and hyperlinked symbols for Lean blueprints.

Load it after the blueprint package:

    \usepackage{blueprint}
    \usepackage[strict]{symbols}

Commands (inside a definition, lemma, theorem, ... or proof):

    \defines{M_e}{matrix in $\mathbb R^{n\times n}$}   this item introduces the symbol M_e, of the given type
    \binds{e,k,l}                                        symbols bound locally here ("for an edge e")
    \defterm{matrix unit}                                this item defines the term; renders as the term itself

After parsing, the checker (leanblueprint_symbols.core) reports undeclared, redeclared and untyped symbols, terms
used before their definition, and explanatory phrases inside statements. It writes, next to the output directory:

    symbols-report.json   the problems
    symbols.diagnose      a \defines line to complete for every undeclared symbol
    blueprint-data.json   items, symbols, dependency edges and status, for other applications

Options:
    strict          stop the build when the checker reports a problem
    status=FILE     JSON {lean declaration name: status}; nodes are coloured from it instead of \leanok
    envs=a+b+c      environments that are items (default: definition, lemma, theorem, proposition, corollary,
                    remark, example, notation, proof)

In the HTML output, every symbol whose declaration is known links to the item that declares it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from plasTeX import Command
from plasTeX.Base.LaTeX import Math as M
from plasTeX.Logging import getLogger
from plasTeX.PackageResource import PackageCss, PackageJs, PackageTemplateDir

from leanblueprint_symbols import core

log = getLogger()
PKG = Path(__file__).parent
STATIC = PKG.parent / "static"
DEFAULT_ENVS = ["definition", "lemma", "theorem", "proposition", "corollary", "remark", "example", "notation",
                "proof"]
STATUS_COLORS = {"verified": ("#1CAC78", "Dark green"), "stated": ("#B0ECA3", "Light green"),
                 "sorry-free": ("#A3D6FF", "Light blue"), "missing": ("#FFAA33", "Orange")}


def _text(x) -> str:
    """The TeX of an argument; plasTeX turns ' into a typographic quote in text arguments: undo that."""
    t = x.source if hasattr(x, "source") else str(x)
    return t.replace("\u2019", "'").replace("\u2018", "`")


def _split(src: str) -> list[str]:
    """Split a comma-separated list at top-level commas (commas inside braces stay)."""
    out, depth, cur = [], 0, ""
    for ch in src:
        depth += {"{": 1, "}": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [re.sub(r"\s+", " ", x).strip() for x in out if x.strip()]


class defines(Command):
    r"""\defines{symbol}{type}"""
    args = "sym type"

    def digest(self, tokens):
        Command.digest(self, tokens)
        sym = re.sub(r"\s+", " ", _text(self.attributes["sym"])).strip()
        self.parentNode.userdata.setdefault("defines", []).append((sym, _text(self.attributes["type"]).strip()))


class binds(Command):
    r"""\binds{a,b,...}"""
    args = "syms"

    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.userdata.setdefault("binds", []).extend(_split(_text(self.attributes["syms"])))


class defterm(Command):
    r"""\defterm{term}"""
    args = "term:str"

    def digest(self, tokens):
        Command.digest(self, tokens)
        node = self.parentNode
        while node is not None and node.nodeName in ("par", "#document-fragment"):
            node = node.parentNode
        self.parentNode.userdata.setdefault("terms", []).append(self.attributes["term"].strip())


def _owner(node, items):
    """The item a node belongs to: the nearest enclosing node that is one of `items` (a set of ids)."""
    while node is not None:
        if id(node) in items:
            return node
        node = node.parentNode
    return None


def ProcessOptions(options, document):
    envs = options.get("envs", "").split("+") if options.get("envs") else DEFAULT_ENVS
    strict = "strict" in options
    status_file = options.get("status")
    document.addPackageResource(PackageTemplateDir(path=PKG / "renderer_templates"))
    document.addPackageResource([PackageCss(path=STATIC / "symbols.css"), PackageJs(path=STATIC / "symbols.js")])
    state = document.userdata.setdefault("symbols", {})

    def collect() -> list:
        nodes = document.getElementsByTagName(tuple(envs))
        ids = {id(n) for n in nodes}
        items = []
        for n in nodes:
            if getattr(n, "tagName", n.nodeName) == "proof":
                parent = n.userdata.get("proves")
                parent_label = parent.id if parent is not None else None
            else:
                parent_label = None
            # \defines etc. digest into the paragraph that holds them: gather from the item's whole subtree
            defs, bnds, terms = list(n.userdata.get("defines", [])), list(n.userdata.get("binds", [])), \
                list(n.userdata.get("terms", []))
            for d in n.allChildNodes if hasattr(n, "allChildNodes") else []:
                if d is n or _owner(d.parentNode, ids) is not n:
                    continue
                defs += d.userdata.get("defines", []) if hasattr(d, "userdata") else []
                bnds += d.userdata.get("binds", []) if hasattr(d, "userdata") else []
                terms += d.userdata.get("terms", []) if hasattr(d, "userdata") else []
            maths = [m for m in n.getElementsByTagName(("math", "displaymath", "equation", "equation*", "align",
                                                         "align*")) if _owner(m.parentNode, ids) is n]
            kind = getattr(n, "tagName", n.nodeName)
            label = n.id
            if re.fullmatch(r"a\d+", label or ""):     # no \label: name it by what it is
                label = f"proof of {parent_label}" if parent_label else kind
            items.append({"label": label, "kind": kind, "defines": defs, "binds": bnds, "terms": terms,
                          "math": [m.source for m in maths], "text": n.textContent, "parent": parent_label,
                          "node": n})
        return items

    def check() -> None:
        items = collect()
        problems = core.check([{k: v for k, v in it.items() if k != "node"} for it in items])
        by_label = {it["label"]: it["node"] for it in items}
        table = {}
        for it in items:
            for sym, ty in it["defines"]:
                table.setdefault(core.key_of(sym), {"sym": sym, "type": ty, "label": it["label"]})
        state.update(items=items, problems=problems, table=table, by_label=by_label)
        outdir = Path(document.userdata.get("working-dir", ".")).resolve()
        (outdir / "symbols-report.json").write_text(json.dumps(problems, indent=1) + "\n")
        diag = sorted({p["detail"].split(" in ")[0] for p in problems if p["kind"] == "undeclared"})
        (outdir / "symbols.diagnose").write_text("".join(f"\\defines{{{d}}}{{}}\n" for d in diag))
        for p in problems:
            log.warning(f"symbols: {p['kind']} in {p['label']}: {p['detail']}")
        log.info(f"symbols: {len(table)} symbols declared, {len(problems)} problems")
        if strict and problems:
            raise SystemExit(f"symbols: {len(problems)} problems (strict); see symbols-report.json")

    document.addPostParseCallbacks(160, check)

    # links: every math node's MathJax source gets \href around declared symbols
    def resolve(key):
        entry = state.get("table", {}).get(key) or (state.get("table", {}).get((key[0], key[1], "")))
        if entry is None:
            return None
        node = state["by_label"].get(entry["label"])
        url = getattr(node, "url", None) if node is not None else None
        return url or (f"#{entry['label']}" if entry["label"] else None)

    for cls in (M.MathEnvironment, M.math):
        prop = cls.__dict__.get("mathjax_source")
        if prop is None or cls.__dict__.get("_symbols_linked", False):
            continue

        def make(orig):
            def linked(self):
                src = orig.fget(self)
                try:
                    return core.link(src, resolve)
                except Exception:   # never break rendering over a link
                    return src
            return property(linked)
        setattr(cls, "mathjax_source", make(prop))
        cls._symbols_linked = True

    # status colours from the verifier, when given
    if status_file:
        status = json.loads(Path(status_file).read_text())
        dep = document.userdata.setdefault("dep_graph", {})

        def node_status(node):
            decls = node.userdata.get("leandecls", [])
            if not decls:
                return None
            st = [status.get(d, "missing") for d in decls]
            for s in ("missing", "stated", "sorry-free"):
                if s in st:
                    return s
            return "verified"

        def colorizer(node):
            s = node_status(node)
            return STATUS_COLORS[s][0] if s else ""

        def apply_status():
            dep["colorizer"] = colorizer
            dep["fillcolorizer"] = colorizer
            dep.setdefault("legend", []).append(
                ("colours", "from the project verifier: dark green = verified, light green = stated, light blue = "
                            "sorry-free (not verified), orange = Lean declaration missing"))
            state["node_status"] = node_status

        document.addPostParseCallbacks(170, apply_status)

    # machine-readable output
    def export() -> None:
        items = state.get("items", [])
        out = {"items": [], "symbols": [], "problems": state.get("problems", [])}
        for it in items:
            n = it["node"]
            uses = [u.id for u in n.userdata.get("uses", [])]
            out["items"].append({"label": it["label"], "kind": it["kind"],
                                 "title": _text(n.title) if getattr(n, "title", None) else None,
                                 "lean": n.userdata.get("leandecls", []), "uses": uses, "parent": it["parent"],
                                 "defines": [s for s, _ in it["defines"]], "terms": it["terms"],
                                 "status": state["node_status"](n) if "node_status" in state else None})
        for key, e in state.get("table", {}).items():
            out["symbols"].append({"sym": e["sym"], "type": e["type"], "label": e["label"]})
        outdir = Path(document.userdata.get("working-dir", ".")).resolve()
        (outdir / "blueprint-data.json").write_text(json.dumps(out, indent=1) + "\n")

    document.addPostParseCallbacks(180, export)
