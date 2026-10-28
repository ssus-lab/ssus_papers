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
repo's own name — copying this repo root into a project as
`_extensions/ssus_papers` leaves `format: ssus-masthead-pdf` with no
extension to read. Vendor the inner folder:

    cp -R ~/Dropbox/projects/ssus_papers/_extensions/ssus-masthead <project>/_extensions/

Re-copy **in full** whenever the source changes: a partial re-sync leaves a
stale vendor and quarto silently falls back to plain pdf/html. This repo is
the canonical source; the copies in `ssus_paper_template/paper/_extensions/`
and `kindex/paper-pnas/_extensions/` are vendors.

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

Both families are vendored in `_extensions/ssus-masthead/assets/fonts/`
with their OFL licenses — nothing is fetched at render or view time, and no
TeX Live font package is needed. Libre Franklin 400/600/800 upright and
italic; IBM Plex Mono 400/500/600 (Medium is the html series line's weight).
The pdf loads them through fontspec
(`Path = _extensions/ssus-masthead/assets/fonts/`); the html's `masthead.css`
declares `@font-face` pointing at the same files — quarto references the css
in place from the vendor, so the urls resolve beside it.

## Attribution

`include-in-header.tex` and the `before-body`/`before-title` partials are
adapted copies from the hikmah core
([andrewheiss/hikmah-academic-quarto](https://github.com/andrewheiss/hikmah-academic-quarto)
v0.0.7, MIT), retyped to the SSUS brand and recolored to the brand palette,
with the centered title block replaced by the identity sheet's Surface-02
masthead — mark, series line, title, authors numbered to their affiliations,
and a footer rule carrying the lab line and the date on every page.