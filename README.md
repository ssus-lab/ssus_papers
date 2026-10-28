# ssus-masthead

The working-paper masthead format of Spatial Science and Urban Systems: a
Quarto extension contributing `ssus-masthead-pdf` and `ssus-masthead-html`.
It is the display format of Eli's paper template, `ssus_paper_template`: the
prose is written once, and every copy a paper needs over its life — working
paper, blinded manuscript, publisher-class, track-changes — is a profile over
that prose. This extension builds the working-paper copy, the one
spatialscience.org links as a preprint.

Built from the hikmah core
([andrewheiss/hikmah-academic-quarto](https://github.com/andrewheiss/hikmah-academic-quarto)
v0.0.7, MIT): `include-in-header.tex` and the `before-body`/`before-title`
partials are adapted copies, retyped to the SSUS brand and recolored to the
brand palette, with the centered title block replaced by the identity
sheet's Surface-02 masthead — mark, series line, title, authors numbered to
their affiliations, and a footer rule carrying the lab line and the date on
every page. The html target overrides quarto's `title-block.html` partial
and matches the pdf on screen, dark-mode automatic under
`prefers-color-scheme`.

## Use

The extension is vendored, not installed. This repo is the canonical
source; copy it into a project's `_extensions/`:

    cp -R ~/Dropbox/projects/ssus-masthead <project>/_extensions/ssus-masthead

Re-copy **in full** whenever the source changes: a partial re-sync leaves a
stale vendor and quarto silently falls back to plain pdf/html. The two
targets differ in bibliography handling — `assets/apa.csl` (DOIs printed,
the APA print convention) for the pdf, `assets/apa-web.csl`
(source-DOI-URL neutralized, titles hyperlinked) for the html; both are real
APA.

Set `format: ssus-masthead-pdf` or `ssus-masthead-html` and write the
document. Options:

| Option | Target | Effect |
|---|---|---|
| `masthead-typographic: true` | both | the Surface-02-E stacked label instead of the mark |
| `masthead-series: "…"` | both | the mono series line; default `SSUS working paper series` |
| `masthead-mark-file: path.pdf` | pdf only | a different mark; the html embeds the canonical mark inline |

## Fonts

Libre Franklin 400/600/800 is vendored in `assets/fonts/` with its OFL
license. IBM Plex Mono is not vendored: the pdf target loads it from TeX
Live (`ibmplex`, SemiBold as its 600 weight), the html target from Google
Fonts (the `@import` in `masthead.css`).