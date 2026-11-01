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
    status=FILE     JSON {lean declaration name: status} or {name: {"status": ..., "url": ...}}; nodes are coloured
                    from it instead of \leanok, and a given url replaces the declaration's documentation link
    reader          the reader theme: a reading column, light and dark, a contents panel and text size (reader.css,
                    reader.js; also styles the dependency graph page)
    css=URL         one more stylesheet linked from every page (e.g. locally served fonts)
    approve         an Approve button at the foot of each labelled card, bound to a hash of the card's source (its
                    proof included); approvals live in the browser, or with a host page that provides
                    window.symbolsApprovalHost (see symbols.js)
    envs=a+b+c      environments that are items (default: definition, lemma, theorem, proposition, corollary,
                    remark, example, notation, proof)

Every lemma, theorem, proposition and corollary carries a chip saying what its proof is: "verified in Lean" (every
Lean declaration it names is verified, by the status file, or \leanok without one), "proof on paper" (a proof
follows it in the text), or "no proof yet"; a conjecture's chip says "open".

In the HTML output, every symbol whose declaration is known links to the item that declares it; following such a link
opens a preview of the item in place (symbols.js), with "Go to" and "Back to where you were".
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from plasTeX import Command
from plasTeX.Base.LaTeX import Math as M
from plasTeX.Logging import getLogger
from plasTeX.PackageResource import PackageCss, PackageJs, PackageProcessFilecontents, PackageTemplateDir

from jinja2 import Template

from leanblueprint_symbols import core

log = getLogger()
PKG = Path(__file__).parent
STATIC = PKG.parent / "static"
DEFAULT_ENVS = ["definition", "lemma", "theorem", "proposition", "corollary", "conjecture", "remark", "example",
                "notation", "proof"]
# what a statement's heading says about its proof (the chip), most established first
PROOF_STATES = {"verified": "verified in Lean", "paper": "proof on paper", "none": "no proof yet", "open": "open"}
PROOF_KINDS = {"lemma", "theorem", "proposition", "corollary"}
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
    reader = "reader" in options
    extra_css = options.get("css")
    res = [PackageCss(path=STATIC / "symbols.css"), PackageJs(path=STATIC / "symbols.js")]
    if reader:
        res += [PackageCss(path=STATIC / "reader.css"), PackageJs(path=STATIC / "reader.js")]
    document.addPackageResource(res)

    def head_links(doc, s: str) -> str:
        """Every HTML page (the dependency graph pages too, which the package resources do not reach) links the
        reader theme and the extra stylesheet once."""
        if "</head>" not in s:
            return s
        add = ""
        if extra_css and extra_css not in s:
            add += f'<link rel="stylesheet" href="{extra_css}" />\n'
        if reader and "styles/reader.css" not in s:
            add += '<link rel="stylesheet" href="styles/reader.css" />\n'
        return s.replace("</head>", add + "</head>", 1) if add else s

    if reader or extra_css:
        document.addPackageResource(PackageProcessFilecontents(data=head_links))
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
        raw = json.loads(Path(status_file).read_text())
        status = {k: (v["status"] if isinstance(v, dict) else v) for k, v in raw.items()}
        urls = {k: v["url"] for k, v in raw.items() if isinstance(v, dict) and v.get("url")}
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

        def apply_urls():
            """After leanblueprint's make_lean_data (150): the status file's url for each declaration that has one."""
            for graph in dep.get("graphs", {}).values():
                for node in graph.nodes:
                    node.userdata["lean_urls"] = [(d, urls.get(d, u)) for d, u in node.userdata.get("lean_urls", [])]

        if urls:
            document.addPostParseCallbacks(160, apply_urls)

    # the proof chip on each statement's heading (leanblueprint's header-extras hook)
    def proof_state(node):
        kind = getattr(node, "thmName", None) or getattr(node, "tagName", "")
        if kind == "conjecture":
            return "open"
        if kind not in PROOF_KINDS:
            return None
        decls = node.userdata.get("leandecls", [])
        if "node_status" in state:
            lean_ok = bool(decls) and state["node_status"](node) == "verified"
        else:
            proof = node.userdata.get("proved_by")
            lean_ok = bool(node.userdata.get("leanok")) and (proof is None or bool(proof.userdata.get("leanok")))
        if lean_ok:
            return "verified"
        return "paper" if node.userdata.get("proved_by") is not None else "none"

    def apply_proof_states():
        for node in document.getElementsByTagName(tuple(envs)):
            st = proof_state(node)
            if st:
                node.userdata["symbols_proof"] = st
                node.userdata["symbols_proof_text"] = PROOF_STATES[st]
        state["proof_state"] = lambda n: n.userdata.get("symbols_proof")

    document.addPostParseCallbacks(175, apply_proof_states)

    # a hash of each card's source (with its proof), for approvals bound to what was read
    approve = "approve" in options

    def card_sha(node) -> str:
        src = node.source or ""
        proof = node.userdata.get("proved_by")
        if proof is not None:
            src += "\n" + (proof.source or "")
        return hashlib.sha256(src.encode()).hexdigest()[:16]

    def apply_shas():
        for node in document.getElementsByTagName(tuple(e for e in envs if e != "proof")):
            if node.id and not re.fullmatch(r"a\d+", node.id):
                node.userdata["symbols_sha"] = card_sha(node)
                if approve:
                    node.userdata["symbols_approve"] = True

    document.addPostParseCallbacks(176, apply_shas)
    marker = Template('{% if obj.userdata.symbols_approve %}<span class="sym-approve" hidden data-label="{{ obj.id }}" '
                      'data-sha="{{ obj.userdata.symbols_sha }}"></span>{% endif %}')
    document.userdata.setdefault("thm_header_extras_tpl", []).append(marker)
    chip = Template('{% if obj.userdata.symbols_proof %}<span class="proofchip proofchip-{{ obj.userdata.symbols_proof }}">'
                    '{{ obj.userdata.symbols_proof_text }}</span>{% endif %}')
    document.userdata.setdefault("thm_header_extras_tpl", []).append(chip)

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
                                 "status": state["node_status"](n) if "node_status" in state else None,
                                 "proof": n.userdata.get("symbols_proof"), "sha": n.userdata.get("symbols_sha")})
        for key, e in state.get("table", {}).items():
            out["symbols"].append({"sym": e["sym"], "type": e["type"], "label": e["label"]})
        outdir = Path(document.userdata.get("working-dir", ".")).resolve()
        (outdir / "blueprint-data.json").write_text(json.dumps(out, indent=1) + "\n")

    document.addPostParseCallbacks(180, export)
