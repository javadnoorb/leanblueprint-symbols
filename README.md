# leanblueprint-symbols

Declared, checked and hyperlinked symbols for [Lean blueprints](https://github.com/PatrickMassot/leanblueprint).

A blueprint links each statement to its Lean declaration and draws the dependency graph between statements. This
plugin works one level down, on the symbols inside formulas:

* **Declarations.** An item says which symbols it introduces, with their types: `\defines{M_e}{matrix in $\mathbb R^{n\times n}$}`.
  Symbols bound locally are listed with `\binds{e,k,l}`, and defined terms are marked where they are defined with
  `\defterm{matrix unit}`.
* **Checks at build time.** The checker reports every symbol used before any item declares it, a symbol declared twice
  (one meaning per symbol), a declaration without a type, a defined term used before its definition, and explanatory
  phrases ("i.e.", "so that", ...) inside definitions and statements. `symbols.diagnose` lists a `\defines` line to
  complete for each undeclared symbol; the `strict` option stops the build on any problem.
* **Hyperlinked formulas.** Every declared symbol in every formula links to the item that declares it. Following a
  link opens a preview of that item where you are, with "Go to" and "Back to where you were". A tap that lands a
  few pixels beside a small symbol still counts.
* **Lean status from your own checker.** With `status=FILE`, dependency-graph nodes are coloured from a JSON file
  your project writes (for example from its verifier), not from hand-written `\leanok`. An entry may also give a URL
  for the declaration, which replaces the link to the mathlib documentation.
* **What each statement's proof is.** Every lemma, theorem, proposition and corollary carries a chip: "verified in
  Lean" (each Lean declaration it names is verified, by the status file, or `\leanok` without one), "proof on
  paper" (a proof follows it in the text) or "no proof yet". A `conjecture` environment is an item too; its chip says
  "open". The labels Theorem, Lemma, ... say how much a result matters; the chip says whether it is proved.
* **Approvals** (option `approve`): an Approve button at the foot of each labelled card, bound to a hash of the
  card's source (its proof included), so a card edited after its approval shows "changed since you approved it".
  Approvals stay in the browser unless a host page stores them: a page embedding the text sets
  `window.symbolsApprovalHost = {load, set}` on the text's window and calls `window.symbolsApprovals.refresh()`.
  The hashes are also in `blueprint-data.json` (`items[].sha`).
* **Reader theme** (option `reader`): a reading column, light and dark modes, items set off by kind, a contents panel
  with a filter, the current section, the text size, and item tools that work on touch screens. The dependency graph
  page gets the same theme.
* **Machine-readable output.** `blueprint-data.json` holds the items, their dependencies, Lean names, symbols and
  status for other applications; `symbols-report.json` holds the checker's problems.

## Use

```latex
\usepackage{blueprint}
\usepackage[reader,status=status.json]{symbols}

\begin{definition}[matrix unit]\label{def:matrix-unit}
  \uses{def:wiring}
  \defines{M_e}{matrix in $\mathbb R^{n\times n}$}
  \binds{e,k,l}
  For an edge $e$, the \defterm{matrix unit} of $e$ is $M_e\in\mathbb R^{n\times n}$ with $(M_e)_{kl}=1$ if
  $k=t(e)$ and $l=s(e)$, and $0$ otherwise.
\end{definition}
```

```sh
pip install git+https://github.com/javadnoorb/leanblueprint-symbols
plastex --plugins leanblueprint leanblueprint_symbols -- web.tex
```

### Options

| option | effect |
|---|---|
| `strict` | stop the build when the checker reports a problem |
| `status=FILE` | JSON `{lean name: status}` or `{lean name: {"status": ..., "url": ...}}`; status is `verified`, `stated`, `sorry-free` or `missing` |
| `reader` | the reader theme (reader.css, reader.js), also on the dependency graph page |
| `approve` | an Approve button on each labelled card (see Approvals) |
| `css=URL` | one more stylesheet linked from every page (for example locally served fonts) |
| `envs=a+b+c` | the environments that are items (default: definition, lemma, theorem, proposition, corollary, conjecture, remark, example, notation, proof); add `conjecture` to blueprint's `thms` option to put conjectures in the graph |

### Matching rules

Symbols are matched by a key: the base (a letter, a Greek or other command, `\mathcal X`, `\mathrm{Word}`, an
accented base such as `\tilde H`), whether it carries a subscript, and a decoration superscript (`^-`, `^+`,
`^{\mathrm{nd}}`). A declaration `M_e` therefore covers `M_e`, `M_{e'}` and `M_1`; a plain power `x^2` does not
change the key. Variables bound inside a formula (set-builder notation, big operators, quantifiers) count as bound
there. A proof sees the symbols its statement declares and binds.

The checker core (`leanblueprint_symbols.core`) does not depend on plasTeX: it takes a list of items as dicts and can
serve other front ends.

## Status

Early (0.x). Tested with leanblueprint 0.0.20 and plasTeX 3.1.

## License

Apache-2.0.
