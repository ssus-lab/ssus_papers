# ssus_papers

The repo of the SSUS paper formats: three Quarto extensions that build every
copy a paper needs over its life from prose written once. `ssus-masthead`
contributes `ssus-masthead-pdf` and `ssus-masthead-html`, the working-paper
copy, the one spatialscience.org links as a preprint; `ssus-blind`
contributes `ssus-blind-pdf`, the blinded manuscript, and carries
`submit.sh`, which stages a journal's bundle; `ssus-titlepage` contributes
`ssus-titlepage-pdf`, the separate title page. A paper's project takes them
as a dependency into its `paper/` folder; the project layout is
`ssus_paper_template`.

Install from a release tag:

    quarto add ssus-lab/ssus_papers@v0.0.6

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
identity in a profile of its own; `submit.sh` then takes that profile in
`TITLEPAGE_PROFILE`.

**Self-citations** are kept real in v1 — journals running double-blind
expect a normal reference list and self-references in third person; any
per-journal suppression is a prose edit, not machinery.

**The bundle** — from the project root,
`_extensions/ssus-lab/ssus-blind/submit.sh [manuscript.qmd]` (in this repo,
`_extensions/ssus-blind/submit.sh`) renders both, stages
`submission/` (blind `manuscript.pdf`/`.tex`, `title-page.pdf`/`.tex`,
cover letter if present), collects the .tex's figures preserving its
relative tree — an asset resolving outside the project root FAILS loud —
runs the Editorial-Manager parity compile (`pdflatex` twice in the bundle),
runs the blind-hygiene checklist built from the author block in
`_quarto.yml` (identity strings must be absent from the blind manuscript's
comment-stripped text — preamble and body, up to the reference list — and
present on the title page; email/ORCID/thanks-shaped strings; a fontspec
font command = FAIL; non-ASCII in the body = warning), and writes
`MANIFEST.txt` with the command log, the checklist result, a file inventory
with sha256, and the upload mapping. Environment overrides fit a project's
layout: `OUT_DIR`, `PDF_NAME`, `TEX_NAME`, `TITLEPAGE_PROFILE`, and
`FIGS_FLAT=1` for portals with a flat build directory (ScholarOne's). **Check the target journal's
instructions page before relying on any bundle.**

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