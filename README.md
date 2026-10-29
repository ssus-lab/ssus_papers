# ssus_papers

The repo of the SSUS paper formats. It holds the working-paper masthead,
`ssus-masthead` — a Quarto extension contributing `ssus-masthead-pdf` and
`ssus-masthead-html`, the display format of Eli's paper template
`ssus_paper_template`: the prose is written once, and every copy a paper
needs over its life — working paper, blinded manuscript, publisher-class,
track-changes — is a profile over that prose. The masthead builds the
working-paper copy, the one spatialscience.org links as a preprint.

**The repo name and the extension id are different things.** The extension id
is fixed by the folder inside `_extensions/` (`ssus-masthead`), never by the
repo's own name. Install with

    quarto add ssus-lab/ssus_papers

which lands the extension at `_extensions/ssus-lab/ssus-masthead/` — or
hand-vendor the inner folder to the depth you prefer:

    cp -R ~/Dropbox/projects/ssus_papers/_extensions/ssus-masthead <project>/_extensions/

Any depth works: the pdf target declares its fonts and the mark as
`format-resources`, so quarto copies them beside the render and the extension
carries no path that assumes where it sits. (Copying the repo root itself as
`_extensions/ssus_papers` is the one layout that breaks — the format needs the
`ssus-masthead` folder.) Re-copy **in full** whenever the source changes: a
partial re-sync leaves a stale vendor and quarto silently falls back to plain
pdf/html.

A pdf render scatters the copied fonts and mark beside the input — ignore
them at the project root so git does not see the byproducts (rooted patterns,
so a vendored extension's own files stay addable):

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
files — quarto references the css from the vendor, so the urls resolve
beside it.

## Attribution

`include-in-header.tex` and the `before-body`/`before-title` partials are
adapted copies from the hikmah core
([andrewheiss/hikmah-academic-quarto](https://github.com/andrewheiss/hikmah-academic-quarto)
v0.0.7, MIT), retyped to the SSUS brand and recolored to the brand palette,
with the centered title block replaced by the identity sheet's Surface-02
masthead — mark, series line, title, authors numbered to their affiliations,
and a footer rule carrying the lab line and the date on every page.