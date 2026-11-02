"""ssus_papers.tables — one table, three typesetting languages.

Analysis writes raw outputs (CSV); a project's formatting script reads them,
formats the numbers into cell strings, and builds a `Table`. This module is
presentation only: it never computes, rounds, or reorders a result.

`Table.to_quarto()` returns a Quarto include — a cross-referenceable
`::: {#tbl-label}` div holding the table three times, as raw LaTeX, typst,
and HTML blocks, with the caption in the div itself. Each writer keeps its
own raw block and drops the others, so one include serves the LaTeX pdf
(the blind manuscript), typst (a typst working paper, qdiff's track-changes
copy), and html.

Cells and captions are Markdown (inline math in `$...$`). One pandoc call
per target converts every distinct cell, so escaping and math follow
pandoc's own writers.

Two Quarto lessons from rentpanel's make_tables.py, kept here:
  - the caption lives in the div, never inside a raw block: Quarto's crossref
    filter re-parses a raw-block caption as Markdown and breaks it;
  - a wide table goes landscape with pdflscape, whose environment rotates
    whole pages, so a longtable inside still breaks across them.

The LaTeX needs booktabs and longtable loaded (pandoc's template loads them
only when the document has a Markdown table) and pdflscape for landscape.
A long typst table needs the format's
`#show figure.where(kind: "quarto-float-tbl"): set block(breakable: true)`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_ALIGN = {"l": ("l", "left", "left"), "c": ("c", "center", "center"),
          "r": ("r", "right", "right")}
_MINUS = re.compile(r"(?<![\w.])-(?=\d)")       # a leading minus on a number


@dataclass
class Table:
    """A booktabs-style table.

    label    crossref id without the `tbl-` prefix
    caption  Markdown; set in the div, above the table
    header   the bottom header row, one Markdown cell per column
    rows     body rows, each a list of Markdown cells, already formatted
    align    one letter per column: l, c, or r
    top      an optional upper header row as (text, colspan) pairs covering
             every column; a cell spanning two or more columns gets a
             trimmed rule beneath it (booktabs' \\cmidrule(lr))
    groups   indices of body rows that open a new panel (a gap before each)
    size     point size of the table text
    colsep   space between columns, in points
    landscape  rotate the table onto its own page (LaTeX, typst)
    """

    label: str
    caption: str
    header: list[str]
    rows: list[list[str]]
    align: str
    top: list[tuple[str, int]] = field(default_factory=list)
    groups: list[int] = field(default_factory=list)
    size: float = 8.0
    colsep: float = 6.0
    landscape: bool = False

    def __post_init__(self):
        n = len(self.align)
        if len(self.header) != n or any(len(r) != n for r in self.rows):
            raise ValueError("header and every row need one cell per column")
        if self.top and sum(span for _, span in self.top) != n:
            raise ValueError("the top row's spans must cover every column")

    # ------------------------------------------------------------- helpers

    @property
    def ncol(self) -> int:
        return len(self.align)

    def _spans(self):
        """(first column, one past the last, text) for each top cell."""
        col = 0
        for text, span in self.top:
            yield col, col + span, text
            col += span

    def _cells(self) -> list[str]:
        out = list(self.header) + [c for r in self.rows for c in r]
        out += [text for text, _ in self.top]
        return out

    # ------------------------------------------------------------- writers

    def to_latex(self) -> str:
        cv = _convert(self._cells(), "latex")
        colspec = "".join(_ALIGN[a][0] for a in self.align)
        head = []
        if self.top:
            cells, rules = [], []
            for a, b, text in self._spans():
                if b - a > 1:
                    cells.append(rf"\multicolumn{{{b - a}}}{{c}}{{{cv[text]}}}")
                    if text:
                        rules.append(rf"\cmidrule(lr){{{a + 1}-{b}}}")
                else:
                    cells.append(cv[text])
            head += [" & ".join(cells) + r" \\", " ".join(rules)]
        head.append(" & ".join(cv[c] for c in self.header) + r" \\")
        head = "\n".join(h for h in head if h)
        body = []
        for i, row in enumerate(self.rows):
            if i in self.groups and i > 0:
                body.append(r"\addlinespace")
            body.append(" & ".join(_minus(cv[c], "latex") for c in row) + r" \\")
        lead = round(self.size * 1.2, 1)
        out = [
            rf"\begingroup\fontsize{{{self.size}}}{{{lead}}}\selectfont",
            rf"\setlength{{\tabcolsep}}{{{self.colsep / 2}pt}}",
            rf"\begin{{longtable}}{{{colspec}}}",
            r"\toprule", head, r"\midrule", r"\endfirsthead",
            r"\toprule", head, r"\midrule", r"\endhead",
            rf"\midrule \multicolumn{{{self.ncol}}}{{r}}"
            r"{\footnotesize\itshape continued on next page} \\",
            r"\endfoot", r"\bottomrule", r"\endlastfoot",
            *body,
            r"\end{longtable}", r"\endgroup",
        ]
        return "\n".join(out)

    def to_typst(self) -> str:
        cv = _convert(self._cells(), "typst")
        align = ", ".join(_ALIGN[a][1] for a in self.align)
        head = ["table.hline(stroke: 0.8pt),"]
        if self.top:
            for a, b, text in self._spans():
                if b - a > 1:
                    head.append(f"table.cell(colspan: {b - a}, align: center)[{cv[text]}],")
                else:
                    head.append(f"[{cv[text]}],")
            for a, b, text in self._spans():
                if b - a > 1 and text:
                    # with a column gutter, a rule from a to b stops short of
                    # its neighbors' rules: \cmidrule(lr)'s trimmed ends
                    head.append(f"table.hline(start: {a}, end: {b}, stroke: 0.4pt),")
        head.append(" ".join(f"[{cv[c]}]," for c in self.header))
        head.append("table.hline(stroke: 0.5pt),")
        body = []
        for i, row in enumerate(self.rows):
            if i in self.groups and i > 0:
                body.append(f"table.cell(colspan: {self.ncol}, inset: 0pt)[#v(0.5em)],")
            cells = (_nowrap_typst(_minus(cv[c], "typst")) for c in row)
            body.append(" ".join(f"[{c}]," for c in cells))
        inner = "\n".join([
            "#{",
            f"  set text(size: {self.size}pt)",
            "  set par(justify: false)",
            "  table(",
            f"    columns: {self.ncol},",
            f"    align: ({align},),",
            f"    inset: (x: {self.colsep / 4}pt, y: 0.3em),",
            f"    column-gutter: {self.colsep / 2}pt,",
            "    stroke: none,",
            "    table.header(",
            *("      " + h for h in head),
            "    ),",
            *("    " + b for b in body),
            "    table.hline(stroke: 0.8pt),",
            "  )",
            "}",
        ])
        return inner

    def to_html(self) -> str:
        cv = _convert(self._cells(), "html")
        em = round(self.size / 11, 3)
        pad = f"0.15em {self.colsep / 2}pt"
        rule = "border-top: 1.5px solid currentColor"

        def cell(tag, text, a, extra=""):
            style = f"text-align: {_ALIGN[a][2]}; padding: {pad};{extra}"
            return f'<{tag} style="{style}">{text}</{tag}>'

        rows = []
        if self.top:
            tr = []
            for a, b, text in self._spans():
                if b - a > 1:
                    inner = (f'<span style="display: block; border-bottom: 1px solid '
                             f'currentColor; margin: 0 {self.colsep / 2}pt;">{cv[text]}</span>')
                    tr.append(f'<th colspan="{b - a}" style="text-align: center; '
                              f'padding: {pad}; font-weight: normal;">{inner}</th>')
                else:
                    tr.append(cell("th", cv[text], self.align[a], " font-weight: normal;"))
            rows.append(f'<tr style="{rule}">' + "".join(tr) + "</tr>")
        tr = [cell("th", cv[c], a, " font-weight: normal;")
              for c, a in zip(self.header, self.align)]
        style = "border-bottom: 1px solid currentColor;" + ("" if self.top else rule)
        rows.append(f'<tr style="{style}">' + "".join(tr) + "</tr>")
        head = "<thead>" + "".join(rows) + "</thead>"
        body = []
        for i, row in enumerate(self.rows):
            gap = " padding-top: 0.7em;" if i in self.groups and i > 0 else ""
            tds = [cell("td", _minus(cv[c], "html"), a, " white-space: nowrap;" + gap)
                   for c, a in zip(row, self.align)]
            body.append("<tr>" + "".join(tds) + "</tr>")
        return (
            f'<table class="ssus-table" data-quarto-disable-processing="true" '
            f'style="font-size: {em}em; border-collapse: collapse; '
            f'border-bottom: 1.5px solid currentColor; margin: 0 auto;">'
            f"{head}<tbody>{''.join(body)}</tbody></table>"
        )

    def to_quarto(self) -> str:
        blocks = [
            "```{=latex}\n" + self.to_latex() + "\n```",
            "```{=typst}\n" + self.to_typst() + "\n```",
            "```{=html}\n" + self.to_html() + "\n```",
        ]
        div = f"::: {{#tbl-{self.label}}}\n" + "\n\n".join(blocks) + \
            f"\n\n{self.caption}\n:::\n"
        if self.landscape:
            # Quarto's landscape div: pdflscape in LaTeX, a flipped page in
            # typst, so the caption turns with the table
            div = "::::: {.landscape}\n\n" + div + "\n:::::\n"
        return div

    def write(self, path) -> Path:
        path = Path(path)
        path.write_text(self.to_quarto(), encoding="utf-8")
        return path


# ----------------------------------------------------------------- pandoc


def _pandoc() -> list[str]:
    exe = shutil.which("pandoc")
    return [exe] if exe else ["quarto", "pandoc"]


def _convert(cells: list[str], to: str) -> dict[str, str]:
    """Map each distinct Markdown cell to its inline rendering in `to`.

    The cells travel as one bullet list, one item per cell, so a single
    pandoc call converts them all and the items come back in order.
    """
    uniq = sorted({c for c in cells if c.strip()})
    out = {"": ""}
    if not uniq:
        return out
    md = "\n".join("- " + c.replace("\n", " ") for c in uniq) + "\n"
    res = subprocess.run(_pandoc() + ["-f", "markdown", "-t", to, "--wrap=none"],
                         input=md, capture_output=True, text=True, check=True)
    text = res.stdout
    if to == "latex":
        # pandoc sets each \item on its own line, the content on the next
        body = text.split(r"\tightlist", 1)[-1].rsplit(r"\end{itemize}", 1)[0]
        items = [" ".join(p.split())
                 for p in re.split(r"(?m)^\s*\\item\b", body)[1:]]
    elif to == "typst":
        items = [ln.lstrip()[2:].strip()
                 for ln in text.splitlines() if ln.lstrip().startswith("- ")]
    else:
        items = re.findall(r"<li>(.*?)</li>", text, flags=re.S)
    if len(items) != len(uniq) or not all(items):
        raise RuntimeError(f"pandoc returned {sum(map(bool, items))} non-empty cells "
                           f"for {len(uniq)} ({to})")
    out.update(zip(uniq, items))
    return out


def _minus(s: str, to: str) -> str:
    """A leading hyphen on a number becomes a true minus sign."""
    sub = {"latex": "$-$", "typst": "−", "html": "&minus;"}[to]
    return _MINUS.sub(sub, s)


def _nowrap_typst(s: str) -> str:
    """Typst wraps a cell that does not fit where LaTeX overflows; keep body
    cells on one line by making their spaces non-breaking (outside math)."""
    parts = re.split(r"(\$[^$]*\$)", s)
    return "".join(p if p.startswith("$") else p.replace(" ", "~") for p in parts)
