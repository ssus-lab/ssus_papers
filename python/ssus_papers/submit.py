"""Stage a journal's upload bundle from the rendered blind manuscript and title page.

Run it from the paper's Quarto project root, after both renders:

    quarto render paper.qmd --profile blind --to ssus-blind-pdf
    quarto render title-page.qmd --to ssus-titlepage-pdf
    python -m ssus_papers.submit paper.qmd

A project in the ssus_paper_template layout runs all three as
`pixi run submit`. This module renders nothing and touches no git state.

It copies the blind manuscript (pdf and tex), the title page (pdf and tex),
a cover letter if one is rendered, and every figure the manuscript's tex
includes into ``submission/``; strips the two guarded package loads that
journal portals' tex scanners flag as missing; runs the blind-hygiene
checklist, built from the identity in ``_quarto.yml``; and writes
``MANIFEST.txt``. It exits 1 on any failure.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Journal portals' tex scanners read \usepackage tokens without honoring
# \IfFileExists, so pandoc's two guarded optional loads read as required
# packages and are flagged [Missing] against the journal's TeX Live
# (Sociological Methods & Research's ScholarOne build, 2026-11: both). The
# footnotehyper guard becomes its own fallback (footnote also provides the
# \makesavenoteenv{longtable} the template keeps); xurl only relaxed URL
# breaking and the formats load url themselves, so its guard goes.
FOOTNOTEHYPER = re.compile(
    r"^\\IfFileExists\{footnotehyper\.sty\}"
    r"\{\\usepackage\{footnotehyper\}\}\{\\usepackage\{footnote\}\}\s*(?:%[^\n]*)?\n",
    re.M,
)
XURL = re.compile(
    r"^\s*\\IfFileExists\{xurl\.sty\}\{\\usepackage\{xurl\}\}\{\}\s*(?:%[^\n]*)?\n",
    re.M,
)
INCLUDEGRAPHICS = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\{)([^}]*)\}")
FIGURE_SUFFIXES = ("", ".pdf", ".png", ".jpg", ".jpeg", ".eps")


def strip_portal_guards(tex: str) -> tuple[str, bool]:
    """Remove the guarded footnotehyper and xurl loads.

    Returns the new text and whether either name survives the strip, which
    means pandoc's template drifted and the patterns need updating.
    """
    tex = FOOTNOTEHYPER.sub(r"\\usepackage{footnote}\n", tex)
    tex = XURL.sub("", tex)
    return tex, re.search(r"footnotehyper|xurl", tex) is not None


def figure_paths(tex: str) -> list[str]:
    """The paths every \\includegraphics names, in order, without repeats."""
    return list(dict.fromkeys(m.group(2) for m in INCLUDEGRAPHICS.finditer(tex)))


def flatten_figures(tex: str) -> str:
    """Rewrite every \\includegraphics path to its bare filename.

    For portals that compile every upload in one flat directory, as
    ScholarOne does.
    """
    return INCLUDEGRAPHICS.sub(lambda m: m.group(1) + Path(m.group(2)).name + "}", tex)


def resolve_figure(path: str, root: Path) -> Path | None:
    """The file a tex figure path names, tried with the usual suffixes.

    None when no candidate exists or the file resolves outside ``root``:
    a bundle carries only what is inside the project.
    """
    root = root.resolve()
    for suffix in FIGURE_SUFFIXES:
        cand = (root / (path + suffix)).resolve()
        if cand.is_file():
            return cand if cand.is_relative_to(root) else None
    return None


# Where the reference list starts. Self-citations stay real, so the
# checklist reads the body only up to the first of these.
REFERENCE_MARKS = (
    r"\begin{CSLReferences}",
    r"\section*{References}",
    r"\section{References}",
    r"\section*{Bibliography}",
    r"\section{Bibliography}",
    r"\bibliography{",
    r"\printbibliography",
)


def blind_body(tex: str) -> str:
    """The text the checklist reads: comments dropped, preamble to references.

    LaTeX comments (a format's own provenance text) are not manuscript
    content. The cut at the reference list is sought only after
    begin-document: pandoc's preamble defines the CSLReferences
    environment, and cutting at that definition once left the whole body
    unchecked (kindex's SMR bundle, 2026-11-01).
    """
    lines = (line.lstrip() for line in tex.splitlines(keepends=True))
    text = "".join(line for line in lines if not line.startswith("%"))
    start = max(text.find(r"\begin{document}"), 0)
    cuts = [i for i in (text.find(mark, start) for mark in REFERENCE_MARKS) if i >= 0]
    return text[: min(cuts)] if cuts else text


def identity_strings(quarto_yml: str) -> list[tuple[str, str]]:
    """The identity the blind copy must omit, read from ``_quarto.yml``.

    Each ``name:`` value (authors and affiliations) is tagged ``name``: it
    must be absent from the blind body and present on the title page. The
    local part of each ``email:`` is tagged ``email``: absent from the blind
    body only, since the title page prints the corresponding author's alone.
    Strings of two characters or fewer are skipped.
    """
    found = []
    for kind, key in (("name", "name"), ("email", "email")):
        for value in re.findall(rf"^[\s\-]*{key}: ([^\n]+)", quarto_yml, re.M):
            s = value.strip().strip('"')
            if kind == "email":
                s = s.split("@")[0].strip()
            if len(s) > 2:
                found.append((kind, s))
    return found


# Patterns that must not match the blind body, with what each one means.
BLIND_PATTERNS = (
    (r"\\thanks\{", r"\thanks{"),
    (r"[Aa]cknowledg", "acknowledg"),
    (r"[Ww]e thank", "we thank"),
    (r"[Ww]e are grateful", "we are grateful"),
    (r"[Ff]unded by", "funded by"),
    (r"[Ss]upported by", "supported by"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "an email-like string"),
    (r"[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]", "an ORCID-shaped string"),
    (r"\\set(?:main|sans|mono|math)font", "a fontspec font command (pdflatex cannot run it)"),
)


def check(body: str, title_page: str, identity: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    """The blind-hygiene checklist: (failures, warnings)."""
    failures, warnings = [], []
    for kind, s in identity:
        if s in body:
            failures.append(f"{s} appears in the blind manuscript")
        if kind == "name" and s not in title_page:
            warnings.append(f"{s} not found in the title page (check its block)")
    for pattern, label in BLIND_PATTERNS:
        if re.search(pattern, body):
            failures.append(f"{label} in the blind manuscript")
    if any(ord(ch) > 127 for ch in body):
        warnings.append("non-ASCII characters in the blind manuscript body")
    return failures, warnings


class StageError(Exception):
    """A bundle that cannot be built: a missing render or an outside figure."""


def stage(root: Path, manuscript: str, *, bundle: str = "submission",
          pdf: str = "blind.pdf", out_dir: str = "", flat: bool = False) -> Path:
    """Copy the upload files into ``root/bundle`` and return its path.

    ``pdf`` is the blind render's output (ssus-blind writes blind.pdf);
    ``out_dir`` is the project's output-dir, where the pdfs land, while
    keep-tex leaves each .tex beside its input.
    """
    stem = Path(manuscript).stem
    out = root / out_dir
    sources = {
        "manuscript.pdf": out / pdf,
        "manuscript.tex": root / f"{stem}.tex",
        "title-page.pdf": out / "title-page.pdf",
        "title-page.tex": root / "title-page.tex",
    }
    missing = [str(p.relative_to(root)) for p in sources.values() if not p.is_file()]
    if missing:
        raise StageError("not rendered: " + ", ".join(missing)
                         + " (run the blind and title-page renders first; keep-tex must stay on)")
    dest = root / bundle
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name, src in sources.items():
        shutil.copy2(src, dest / name)
    for letter in (out / "cover_letter.pdf", root / "cover_letter.pdf"):
        if letter.is_file():
            shutil.copy2(letter, dest / letter.name)
            break

    tex_path = dest / "manuscript.tex"
    tex = tex_path.read_text(encoding="utf-8")
    for p in figure_paths(tex):
        src = resolve_figure(p, root)
        if src is None:
            raise StageError(f"figure {p} resolves nowhere inside the project; move it in")
        if not flat and ".." in Path(p).parts:
            raise StageError(f"figure {p} climbs out of the tex's folder, so the bundle "
                             "cannot keep its path; move it in, or pass --flat")
        target = Path(p).name if flat else p
        if not Path(target).suffix:
            target += src.suffix
        (dest / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest / target)
    if flat:
        tex_path.write_text(flatten_figures(tex), encoding="utf-8")

    for name in ("manuscript.tex", "title-page.tex"):
        path = dest / name
        text, drifted = strip_portal_guards(path.read_text(encoding="utf-8"))
        path.write_text(text, encoding="utf-8")
        if drifted:
            print(f"WARN  {name}: footnotehyper/xurl still mentioned after the strip "
                  "(pandoc's template drifted; update ssus_papers.submit's patterns)")
    return dest


def write_manifest(dest: Path, failures: list[str], warnings: list[str]) -> None:
    """MANIFEST.txt: the checklist's result and every file with its sha256."""
    lines = [f"submission bundle — {datetime.now():%Y-%m-%d %H:%M}",
             "checklist: " + ("ALL PASS" if not failures else "FAILURES — DO NOT SUBMIT")]
    lines += [f"  FAIL  {f}" for f in failures] + [f"  WARN  {w}" for w in warnings]
    lines.append("files:")
    for path in sorted(p for p in dest.rglob("*") if p.is_file() and p.name != "MANIFEST.txt"):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"  {digest}  {path.relative_to(dest)}")
    lines += ["",
              "upload: manuscript.tex (or manuscript.pdf) and each figure file;",
              "title-page.pdf in its own field; the cover letter where asked.",
              "CHECK THE TARGET JOURNAL'S INSTRUCTIONS PAGE BEFORE RELYING ON THIS BUNDLE."]
    (dest / "MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ssus_papers.submit",
        description="Stage the submission bundle from the rendered blind manuscript and title page.")
    parser.add_argument("manuscript", nargs="?", default="paper.qmd",
                        help="the manuscript's source, which names its .tex (default: paper.qmd)")
    parser.add_argument("--bundle", default="submission", help="the bundle folder (default: submission)")
    parser.add_argument("--pdf", default="blind.pdf", help="the blind render's pdf (default: blind.pdf)")
    parser.add_argument("--out-dir", default="", help="the project's output-dir, if it sets one")
    parser.add_argument("--flat", action="store_true",
                        help="bare figure filenames, for portals with a flat build directory (ScholarOne)")
    args = parser.parse_args(argv)

    root = Path.cwd()
    config = root / "_quarto.yml"
    if not config.is_file():
        print("FAIL  no _quarto.yml: run from the paper's Quarto project root")
        return 1
    try:
        dest = stage(root, args.manuscript, bundle=args.bundle, pdf=args.pdf,
                     out_dir=args.out_dir, flat=args.flat)
    except StageError as err:
        print(f"FAIL  {err}")
        return 1
    failures, warnings = check(
        blind_body((dest / "manuscript.tex").read_text(encoding="utf-8")),
        (dest / "title-page.tex").read_text(encoding="utf-8"),
        identity_strings(config.read_text(encoding="utf-8")),
    )
    for f in failures:
        print(f"FAIL  {f}")
    for w in warnings:
        print(f"WARN  {w}")
    write_manifest(dest, failures, warnings)
    print(("checklist: ALL PASS" if not failures else "checklist: FAILURES — DO NOT SUBMIT")
          + f"; bundle at {dest.relative_to(root)}/, manifest {dest.relative_to(root)}/MANIFEST.txt")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
