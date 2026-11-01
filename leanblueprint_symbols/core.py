"""Checker core for textbook-style mathematical documents (front-end independent).

An *item* is one numbered unit (definition, lemma, theorem, proof, remark, ...) given as a dict:

    {"label": "def:matrix-unit", "kind": "definition",
     "defines": [("M_e", "matrix in $\\mathbb R^{n\\times n}$")],   # symbols this item introduces, with types
     "binds": ["e", "k", "l"],          # symbols bound locally (for an edge e, ...)
     "terms": ["matrix unit"],          # terms this item defines (glossary)
     "math": ["M_e\\in\\mathbb R^{n\\times n}", ...],              # TeX of every formula, in order
     "text": "For an edge $e$, ...",    # the prose (for term and gloss checks)
     "parent": None,                    # for a proof: the label of its statement (inherits its symbols)
     "uses": ["def:wiring"],            # optional: the items it says it depends on (\\uses)
     "parts": 0}                        # optional: the number of numbered parts of a statement (\\item)

`check(items)` returns a list of problems (dicts with "kind", "label", "detail"), in document order:

    undeclared   a symbol used before any item declares it and not bound here
    redeclared   a symbol declared a second time (one meaning per symbol)
    untyped      a declaration without a type
    term-before  a glossary term used in an item before the item that defines it
    gloss        an explanatory phrase inside a definition or statement ("so that", "i.e.", ...)
    local-def    a symbol declared inside a lemma, theorem, remark, proof, ... and used by another item: a definition
                 used elsewhere belongs in a definition (or the notation) of its own
    two-roles    a letter bound with two different types (\\binds{w \\in \\mathcal B} here, \\binds{w \\in E} there) in
                 items that depend on each other: one letter, one role
    uses         a symbol used in an item whose declaring item the item does not depend on (\\uses, directly or
                 through other items; a proof also through its statement); notation items are exempt
    proof-parts  a statement in numbered parts whose proof does not treat each part ("(1)", "(2)", ...)

A bound symbol may carry a type: "w \\in \\mathcal B", "S \\subseteq E" or "w : point of the box" (the symbol
is what comes before the first \\in, \\subseteq or colon).

Symbols are matched by a normalized key: the base (a letter, a Greek or other command, \\mathcal X, \\mathrm{Word},
an accented base such as \\tilde H), whether it carries a subscript, and a decoration superscript (^-, ^+, ^{\\mathrm{nd}}).
A declaration "M_e" therefore covers M_e, M_{e'}, M_1; "A_S" covers A_E and A_{S_J}; "h^-" covers h^-_{K,\\nu}; a
plain power x^2 is not a decoration and does not change the key.
"""
from __future__ import annotations

import re

STANDARD = {
    r"\mathbb R", r"\mathbb N", r"\mathbb Z", r"\mathbb C", r"\mathbb Q",
    r"\dots", r"\ldots", r"\cdots", r"\vdots", r"\ddots", r"\in", r"\notin", r"\ni", r"\sum", r"\prod", r"\int",
    r"\le", r"\ge", r"\leq", r"\geq", r"\neq", r"\ne", r"\times", r"\to", r"\mapsto", r"\subseteq", r"\subset",
    r"\supseteq", r"\cup", r"\cap", r"\setminus", r"\emptyset", r"\varnothing", r"\infty", r"\pm", r"\mp", r"\cdot",
    r"\circ", r"\det", r"\log", r"\exp", r"\max", r"\min", r"\sup", r"\inf", r"\lim", r"\sqrt", r"\frac", r"\dfrac",
    r"\tfrac", r"\partial", r"\nabla", r"\forall", r"\exists", r"\iff", r"\implies", r"\Rightarrow", r"\Leftarrow",
    r"\Leftrightarrow", r"\Longrightarrow", r"\Longleftrightarrow", r"\land", r"\lor", r"\neg", r"\wedge", r"\vee",
    r"\approx", r"\equiv", r"\dashv", r"\vdash", r"\leftrightarrow", r"\mid", r"\sqcup", r"\sqsubseteq", r"\colon", r"\ast", r"\sim", r"\ll", r"\gg", r"\prime", r"\top", r"\square", r"\qquad", r"\quad",
}
LAYOUT = {  # commands that only shape the formula
    r"\left", r"\right", r"\bigl", r"\bigr", r"\Bigl", r"\Bigr", r"\biggl", r"\biggr", r"\big", r"\Big", r"\,",
    r"\;", r"\!", r"\displaystyle", r"\textstyle", r"\limits", r"\nolimits", r"\begin", r"\end", r"\cases",
    r"\\", r"\{", r"\}", r"\|", r"\langle", r"\rangle", r"\lvert", r"\rvert", r"\lVert", r"\rVert", r"\href",
}
ACCENTS = {r"\tilde", r"\hat", r"\bar", r"\overline", r"\underline", r"\widetilde", r"\widehat", r"\vec", r"\dot"}
FONTS = {r"\mathcal", r"\mathbb", r"\mathrm", r"\mathbf", r"\mathsf", r"\mathfrak", r"\operatorname", r"\boldsymbol"}
GLOSS = [r"\bi\.e\.", r"\bso that\b", r"\bin words\b", r"\bthis is why\b", r"\bnote that\b",
         r"\bthis is the only place\b", r"\bin other words\b", r"\bthat is to say\b"]
STATEMENT_KINDS = {"definition", "lemma", "theorem", "proposition", "corollary", "conjecture"}


def _mask(src: str) -> str:
    r"""The same string with regions that hold no symbols blanked out (same length, so positions match):
    words in \text{...}, environment names in \begin{...}/\end{...}, link targets in \href{...}."""
    out = list(src)
    for m in re.finditer(r"\\(?:text|textrm|mbox|textit|textbf)\s*\{[^{}]*\}|\\(?:begin|end)\s*\{[^{}]*\}|"
                         r"\\href\s*\{[^{}]*\}", src):
        for k in range(m.start(), m.end()):
            out[k] = " "
    return "".join(out)


def _group(s: str, i: int) -> tuple[str, int, int]:
    """The argument starting at s[i]: a {braced group}, a \\command, or one character.
    Returns (text, start of text, end of the argument)."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i, i
    if s[i] == "{":
        depth, j = 0, i
        while j < len(s):
            depth += {"{": 1, "}": -1}.get(s[j], 0)
            if depth == 0:
                return s[i + 1:j], i + 1, j + 1
            j += 1
        return s[i + 1:], i + 1, len(s)
    if s[i] == "\\":
        m = re.match(r"\\[A-Za-z]+|\\.", s[i:])
        return m.group(0), i, i + len(m.group(0))
    return s[i], i, i + 1


def _norm(x: str) -> str:
    return re.sub(r"\s+", " ", x).strip()


def scan(src: str) -> list[tuple[tuple[str, bool, str], int, int]]:
    """Every symbol occurrence in a formula: (key, start, end), positions in `src`. A symbol's span covers its whole
    written form, sub- and superscripts included; symbols inside those scripts are listed too (nested spans)."""
    return _scan(_mask(src), 0, len(src))


def _scan(s: str, lo: int, hi: int) -> list:
    out = []
    i = lo
    while i < hi:
        c = s[i]
        start = i
        base = None
        if c == "\\":
            cmd, _, j = _group(s, i)
            if cmd in FONTS:
                arg, _, j = _group(s, j)
                base = f"{cmd}{{{_norm(arg)}}}" if cmd in (r"\operatorname", r"\mathrm") else f"{cmd} {_norm(arg)}"
            elif cmd in ACCENTS:
                arg, a0, j = _group(s, j)
                inner = _scan(s, a0, a0 + len(arg))
                base = f"{cmd} {inner[0][0][0]}" if inner else None
                out.extend(inner[1:])
            elif cmd in LAYOUT or cmd in STANDARD or not cmd[1:].isalpha():
                i = j
                continue
            else:
                base = cmd
            i = j
        elif c.isalpha():
            base, i = c, i + 1
        else:
            i += 1
            continue
        if base is None:
            continue
        has_sub, deco = False, ""
        while True:   # scripts may follow after spaces (plasTeX writes "\\sigma _e")
            k = i
            while k < hi and s[k] == " ":
                k += 1
            if k >= hi or s[k] not in "_^'":
                break
            i = k
            if s[i] == "'":
                base += "'"
                i += 1
                continue
            mark = s[i]
            arg, a0, i = _group(s, i + 1)
            if mark == "_":
                has_sub = True
                out.extend(_scan(s, a0, a0 + len(arg)))
            else:
                a = _norm(arg)
                if a in ("-", "+", r"\top", "*", r"\prime") or a.startswith(r"\mathrm"):
                    deco = a
                else:
                    out.extend(_scan(s, a0, a0 + len(arg)))
        if base not in STANDARD:
            out.append(((base, has_sub, deco), start, i))
    return out


def tokens(src: str) -> list[tuple[str, bool, str]]:
    """The keys of `scan`, in order."""
    return [k for k, _, _ in scan(src)]


def link(src: str, resolve) -> str:
    r"""Wrap each outermost symbol occurrence that `resolve(key)` maps to a URL in \href{url}{...}. Symbols nested in
    the scripts of a linked symbol are left as they are (the outer link covers them)."""
    spans = [(a, b, resolve(k)) for k, a, b in scan(src)]
    spans = [t for t in spans if t[2]]
    spans.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    chosen, end = [], -1
    for a, b, url in spans:
        if a >= end:
            chosen.append((a, b, url))
            end = b
    for a, b, url in reversed(chosen):
        src = src[:a] + r"\href{" + url + "}{" + src[a:b] + "}" + src[b:]
    return src


BINDERS = [
    r"\\\{\s*([A-Za-z](?:_[A-Za-z])?)\s*(?::|\\in|\\mid|\|)",                       # {e : ...}, {x in ...}
    r"\\(?:sum|prod|max|min|sup|inf|bigcup|bigcap|lim)\s*_\{?\s*([A-Za-z](?:_[A-Za-z])?)\s*(?:\\in|=|:|\\to|,|\})",
    r"\\(?:forall|exists)\s*([A-Za-z](?:_[A-Za-z])?)",
]


def bound_in(src: str) -> set:
    """Variables a formula binds itself (set-builder, big operators, quantifiers)."""
    keys = set()
    for pat in BINDERS:
        for m in re.finditer(pat, src):
            keys.add(key_of(m.group(1)))
    return keys


def key_of(decl: str) -> tuple[str, bool, str]:
    t = tokens(decl)
    if not t:
        raise ValueError(f"cannot read a symbol from {decl!r}")
    return t[-1]


def _matches(use, declared: set) -> bool:
    base, sub, deco = use
    # x_i is a component of a declared x: indexing a declared plain symbol is a use of it
    return (use in declared or (base, sub, "") in declared or bool(deco and (base, False, deco) in declared)
            or bool(sub and (base, False, deco) in declared))


BIND_TYPE = re.compile(r"\\in\b|\\subseteq\b|\\colon|:")


def split_bind(b: str) -> tuple[str, str]:
    """A bound symbol and its type, if it carries one: "w \\in \\mathcal B" -> ("w", "\\in \\mathcal B")."""
    m = BIND_TYPE.search(b)
    if not m:
        return b.strip(), ""
    return b[:m.start()].strip(), _norm(b[m.start():].lstrip(":").strip())


def _which(use, declared):
    """The declared key a use resolves to (the same order as _matches), or None."""
    base, sub, deco = use
    for k in (use, (base, sub, ""), (base, False, deco) if deco else None, (base, False, deco) if sub else None):
        if k is not None and k in declared:
            return k
    return None


EXEMPT_FROM_USES = {"notation"}
DEFINING_KINDS = {"definition", "notation"}


def check(items: list[dict]) -> list[dict]:
    problems = _check(items)
    by = {it["label"]: it for it in items}
    # the dependency closure: what each item depends on, directly or through others; a proof through its statement
    deps: dict[str, set] = {}

    def closure(label, seen=()):
        if label in deps:
            return deps[label]
        it = by.get(label)
        out = set()
        if it is None or label in seen:
            return out
        direct = set(it.get("uses", [])) | ({it["parent"]} if it.get("parent") else set())
        for d in direct:
            out |= {d} | closure(d, seen + (label,))
        deps[label] = out
        return out

    declared: dict[tuple, str] = {}
    kinds = {it["label"]: it.get("kind") for it in items}
    users: dict[tuple, set] = {}
    for it in items:
        label = it["label"]
        own = {key_of(sym) for sym, _ in it.get("defines", [])}
        local = {key_of(split_bind(b)[0]) for b in it.get("binds", [])
                 + (by[it["parent"]].get("binds", []) if it.get("parent") in by else [])}
        seen = set()
        for src in it.get("math", []):
            for use in tokens(src):
                k = _which(use, declared)
                if k is None or k in seen or k in own or _matches(use, local) \
                        or use in bound_in(src):
                    continue
                seen.add(k)
                src_label = declared[k]
                users.setdefault(k, set()).add(label)
                if "uses" in it and kinds.get(src_label) not in EXEMPT_FROM_USES and src_label != label \
                        and src_label not in closure(label):
                    problems.append({"kind": "uses", "label": label,
                                     "detail": f"{k[0]} is declared in {src_label}, which {label} does not depend on"})
        for sym, _ in it.get("defines", []):
            declared.setdefault(key_of(sym), label)
    for k, label in declared.items():
        it = by[label]
        if it.get("kind") in DEFINING_KINDS:
            continue
        own_family = {label, it.get("parent")} | {x["label"] for x in items if x.get("parent") == label}
        others = sorted(users.get(k, set()) - own_family)
        if others:
            problems.append({"kind": "local-def", "label": label,
                             "detail": f"{k[0]} is declared inside this {it.get('kind')} and used in {', '.join(others)}: "
                                       "give it a definition of its own"})
    # one letter, one role: the same letter bound with two different types in items that depend on each other
    typed: dict[str, dict] = {}
    for it in items:
        for b in it.get("binds", []):
            sym, ty = split_bind(b)
            if ty:
                typed.setdefault(it["label"], {})[key_of(sym)] = (sym, ty)
    for a in typed:
        for b in typed:
            if a >= b or not (a in closure(b) or b in closure(a)):
                continue
            for k in typed[a].keys() & typed[b].keys():
                if typed[a][k][1] != typed[b][k][1]:
                    problems.append({"kind": "two-roles", "label": b,
                                     "detail": f"{typed[b][k][0]} is {typed[b][k][1]} here and {typed[a][k][1]} in {a}"})
    # a statement in numbered parts: its proof treats each part
    for it in items:
        st = by.get(it.get("parent"))
        n = (st or {}).get("parts", 0)
        if it.get("kind") != "proof" or n < 2:
            continue
        missing = [str(i) for i in range(1, n + 1) if f"({i})" not in it.get("text", "")]
        if missing:
            problems.append({"kind": "proof-parts", "label": it["label"],
                             "detail": f"{st['label']} has {n} parts; the proof has no ({'), ('.join(missing)})"})
    return problems


def _check(items: list[dict]) -> list[dict]:
    problems: list[dict] = []
    declared: dict[tuple, str] = {}          # key -> label of the declaring item
    scope: dict[str, set] = {}               # label -> keys declared or bound in that item
    terms_at: dict[str, int] = {}            # term -> index of the defining item
    for idx, it in enumerate(items):
        for term in it.get("terms", []):
            terms_at.setdefault(term.lower(), idx)
    for idx, it in enumerate(items):
        label = it["label"]
        own = set()
        for sym, ty in it.get("defines", []):
            k = key_of(sym)
            if not str(ty).strip():
                problems.append({"kind": "untyped", "label": label, "detail": sym})
            if k in declared and declared[k] != label:
                problems.append({"kind": "redeclared", "label": label,
                                 "detail": f"{sym} (first declared in {declared[k]})"})
            own.add(k)
        local = {key_of(split_bind(b)[0]) for b in it.get("binds", [])}
        if it.get("parent") in scope:
            local |= scope[it["parent"]]
        visible = set(declared) | own | local
        seen = set()
        for src in it.get("math", []):
            here = visible | bound_in(src)
            for use in tokens(src):
                if use in seen:
                    continue
                seen.add(use)
                if not _matches(use, here):
                    problems.append({"kind": "undeclared", "label": label, "detail": f"{use[0]} in {src.strip()}"})
        for sym, _ in it.get("defines", []):
            declared.setdefault(key_of(sym), label)
        scope[label] = own | local
        text = it.get("text", "")
        for term, at in terms_at.items():
            if at > idx and re.search(r"\b" + re.escape(term) + r"\b", text, re.I):
                problems.append({"kind": "term-before", "label": label,
                                 "detail": f"'{term}' used before {items[at]['label']} defines it"})
        if it.get("kind") in STATEMENT_KINDS:
            for pat in GLOSS:
                m = re.search(pat, text, re.I)
                if m:
                    problems.append({"kind": "gloss", "label": label, "detail": m.group(0)})
    return problems
