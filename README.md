# ssus_papers

The repo of the SSUS paper formats: three Quarto extensions that build every
copy a paper needs over its life from prose written once. `ssus-masthead`
contributes `ssus-masthead-pdf` and `ssus-masthead-html`, the working-paper
copy, the one spatialscience.org links as a preprint; `ssus-blind`
contributes `ssus-blind-pdf`, the blinded manuscript; `ssus-titlepage`
contributes `ssus-titlepage-pdf`, the separate title page. Beside them,
`python/` holds a small package: `ssus_papers.tables` sets a paper's tables
and `ssus_papers.submit` stages a journal's bundle. A paper's project takes
the formats as a dependency into its `paper/` folder and the package into
its pixi environment; the project layout is `ssus_paper_template`.

Start a paper in an empty folder:

    quarto use template ssus-lab/ssus_papers@v0.0.7 --no-prompt

It installs the three formats and copies the starter: `template.qmd`,
renamed after the folder (`paper/paper.qmd`), `title-page.qmd`,
`_quarto.yml`, and `_quarto-blind.yml`. Install into an existing project
from a release tag:

    quarto add ssus-lab/ssus_papers@v0.0.7

All three land at `_extensions/ssus-lab/<name>/`, and `quarto update
extension ssus-lab/ssus_papers` takes a later release. The ref after `@`
must be a tag or a branch; a commit sha does not resolve. Never copy the
folders in by hand: a hand copy, partially re-synced, once left a stale
format, and quarto silently fell back to plain pdf/html. Quarto keeps no
manifest, so the project states which tag it uses.

**The repo name and the extension ids are different things.** Each id is
fixed by its folder inside `_extensions/`, never by the repo's own name.
Any install depth works: the pdf target declares its fonts and the mark as
`format-resources`, so quarto copies them beside the render.

A pdf render scatters the copied fonts and mark beside the input — ignore
them at the project root so git does not see the byproducts (rooted patterns,
so an installed extension's own files stay addable):

    /*.ttf
    /*.otf
    /ssus-mark-light.pdf

The two targets differ in bibliography handling — `assets/apa.csl` (DOIs
printed, the APA print convention) for the pdf, `assets/apa-web.csl`
(source-DOI-URL neutralized, titles hyperlinked) for the html; both are real
APA. The html matches the pdf on screen, dark-mode automatic under
`prefers-color-scheme`.

Set `format: ssus-masthead-pdf` (or render `--to ssus-masthead-html`) and
write the document. Options:

| Option | Target | Effect |
|---|---|---|
| `masthead-typographic: true` | both | the Surface-02-E stacked label instead of the mark |
| `masthead-series: "…"` | both | the mono series line; default `SSUS working paper series` |
| `masthead-mark-file: path.pdf` | pdf only | a different mark; the html embeds the canonical mark inline |

The repo renders its own specimen: `quarto render` for the pdf,
`quarto render --to ssus-masthead-html` for the html.

## Submission: the blind manuscript, the title page, the bundle

The repo carries the template's submission machinery as **two sibling
extension folders** beside `ssus-masthead` (a Quarto format id is
`<folder>-<base>`, so one folder carries one format per base output; the
family is the hikmah pattern — `hikmah`, `hikmah-manuscript`,
`hikmah-response`). They install together, with the masthead.

- **`ssus-blind-pdf`** — the blinded manuscript: article class, 12 pt,
  double-spaced, `pdf-engine: pdflatex` pinned (quarto's default is
  lualatex; the home render is the journal-polarity render), Computer
  Modern, running head "Running head: SHORT TITLE", citeproc with the
  vendored `assets/apa.csl` (references embedded in the .tex — no `.bbl`),
  black links, and the same abstract/keywords/body machinery the display
  copy uses. Line numbers are opt-in (`linenumbers: true`). It omits the
  identity by construction: `blind.lua` drops the author block, `thanks:`,
  funding, and declarations from the metadata before pandoc writes the
  `.tex`, so not even hyperref's `pdfauthor` names an author.
- **`ssus-titlepage-pdf`** — the standalone title page: full title, authors
  with postal affiliations, ORCID (plain URL, not an icon), the
  corresponding author's contact, word count, short title, funding
  statement (`funding-statement:` — plain `funding:` collides with a quarto
  interpretation and reads back as `true`), additional information, and the
  acknowledgments the blind manuscript cannot carry. Labels set in Nimbus
  Sans caps for the brand's label voice without any brand font; drop the
  `helvet` line for a pure-CM page.

**One config, three copies** (the repo's own `_quarto*.yml` are the pattern
to copy): `_quarto.yml` carries everything the copies share — title,
abstract, keywords, date, bibliography, and the full identity (author block
with ORCID and postal affiliations, `thanks:`, `funding-statement:`,
`additional-info:`, `correspondence-prefix:`). The copies decide what they
emit: the masthead prints the authors, the title page prints the whole
block, and the blind format omits it. Quarto profiles merge config, so a key
present in the base cannot be removed by a profile; blinding by profile was
never sound (the rentpanel lesson). `_quarto-blind.yml` carries per-journal
knobs for the submission render, its overrides all top-level (inside
`format:` they leak into the emitted preamble). A paper may still keep its
identity in a profile of its own; its title page then renders with that
profile.

**Self-citations** are kept real in v1 — journals running double-blind
expect a normal reference list and self-references in third person; any
per-journal suppression is a prose edit, not machinery.

**The bundle** — after the blind and title-page renders, run
`python -m ssus_papers.submit [paper.qmd]` from the Quarto project root; in
a project laid out by `ssus_paper_template`, `pixi run submit` runs the two
renders and then this. It stages `submission/`: the blind
`manuscript.pdf`/`.tex`, `title-page.pdf`/`.tex`, and a rendered
`cover_letter.pdf` if there is one. It collects the figures the .tex
includes, keeping their relative paths, and fails on a figure that is
missing or resolves outside the project. It strips the two guarded package
loads (`footnotehyper`, `xurl`) that ScholarOne's tex scanner flags as
missing. It runs the blind-hygiene checklist built from the author block in
`_quarto.yml`: identity strings must be absent from the blind manuscript's
comment-stripped text (preamble and body, up to the reference list) and
present on the title page; email-, ORCID-, and thanks-shaped strings and a
fontspec font command fail; non-ASCII in the body warns. Last, it writes
`MANIFEST.txt` with the checklist result and a sha256 inventory, and it
exits 1 on any failure. Options fit a project's layout: `--out-dir`, `--pdf`
(the blind render's pdf, default `blind.pdf`), `--bundle`, and `--flat` for
portals with a flat build directory (ScholarOne's). It renders and compiles
nothing and touches no git state. **Check the target journal's instructions
page before relying on any bundle.**

## Tables: `ssus_papers.tables`

Analysis writes raw outputs (CSV) and can be rerun at will; a separate
formatting script reads them and builds each table, so formatting touches
presentation only and no result is typed into a manuscript. `python/` holds
the Python side of that step, a package with no dependencies beyond pandoc
on the path (Quarto's bundled copy serves). A project installs it with pixi
from the same tag as the formats:

    pixi add --pypi ssus-papers --git https://github.com/ssus-lab/ssus_papers --tag v0.0.7 --subdirectory python

`Table` takes Markdown cells, already formatted, and writes one Quarto include
holding the table as raw LaTeX, typst, and HTML under a `#tbl-` div, the
caption in the div; each output keeps its own block:

```python
from ssus_papers import Table

Table(
    label="kr",
    caption="Rank-order indices for California's twenty-one metropolitan areas …",
    header=["Region", "Tracts", "$K^R$", "Pseudo p-value", ...],
    rows=rows,                      # lists of formatted strings
    align="lrrrrrrr",
    top=[("", 1), ("SAR", 2), ...], # optional spanners, ruled beneath
    groups=[7, 14],                 # optional panels, a gap before each
    size=9, colsep=10, landscape=False,
).write("paper/_tbl_kr.md")
```

and in the paper, `{{< include _tbl_kr.md >}}`. It draws the booktabs
grammar in each language — spanner rules trimmed like `\cmidrule(lr)`,
panel gaps, a header repeated on later pages — sets true minus signs, and
keeps typst body cells from wrapping. A landscape table goes in Quarto's
`.landscape` div, so the caption turns with it. It never computes or rounds.

The LaTeX needs `booktabs` and `longtable` loaded (pandoc's template loads
them only when a document has a Markdown table); a long typst table needs
`#show figure.where(kind: "quarto-float-tbl"): set block(breakable: true)`.
Not yet: decimal alignment, multirow, notes under the rule, docx, and
"continued on next page" in typst. Tests: `cd python && PYTHONPATH=. pytest`.

## Fonts

Three families are vendored in `_extensions/ssus-masthead/assets/fonts/`
with their OFL licenses — nothing is fetched at render or view time, and no
TeX Live font package is needed. IBM Plex Serif 400/600 upright and italic
sets the body, abstract, footnotes, references, and tables, with IBM Plex
Math for the pdf's mathematics; Libre Franklin 400/600/800 upright and italic
sets the masthead, headings, and captions; IBM Plex Mono 400/500/600 sets
code, data, and the series and footer lines (Medium is the html series
line's weight). Inline code is colored Blueprint, since Plex Serif and Plex
Mono share a skeleton. Plex Serif and Plex Math are TeX Live's OpenType
files (v3.001 and v1.000): Google Fonts' Plex Serif is v2.6 and carries no
Greek. The html keeps its own math method (KaTeX or MathJax). The pdf sets
11 pt on a 6 in measure (1.25 in side margins).
The pdf reads the copies quarto makes beside the render (`format-resources`);
the html's `masthead.css` declares `@font-face` pointing at the in-place
files — quarto references the css from the installed extension, so the urls
resolve beside it.

## Attribution

`include-in-header.tex` and the `before-body`/`before-title` partials are
adapted copies from the hikmah core
([andrewheiss/hikmah-academic-quarto](https://github.com/andrewheiss/hikmah-academic-quarto)
v0.0.7, MIT), retyped to the SSUS brand and recolored to the brand palette,
with the centered title block replaced by the identity sheet's Surface-02
masthead — mark, series line, title, authors numbered to their affiliations,
and a footer rule carrying the lab line and the date on every page.