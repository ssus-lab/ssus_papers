"""Freeze a journal submission: the upload bundle and the source it came from.

After the blind and title-page renders, which write ``_output/blind/`` and
``_output/titlepage/`` in the paper's Quarto project:

    quarto render paper.qmd --profile blind
    quarto render title-page.qmd --profile titlepage
    python -m ssus_papers.submit LABEL --paper paper

A project in the ssus_paper_template layout runs all three as
``pixi run submit LABEL``. This module renders nothing and touches no git
state.

``submissions/LABEL/`` receives the blind manuscript (pdf and tex), the
title page (pdf and tex), a rendered cover letter if there is one, every
figure the manuscript's tex includes, ``MANIFEST.txt``, and ``source/``: a
copy of the paper's Quarto project as rendered (sources, includes, figures,
bibliography, installed extensions), placed at the paper's path, so qdiff
can take it as the old side of a diff (``qdiff submissions/LABEL/source .
--entry paper/paper.qmd --profile blind``). The bundle's tex has the two
guarded package loads journal portals' scanners flag as missing stripped,
and the blind-hygiene checklist, built from the identity in ``_quarto.yml``,
must pass. A submission is frozen once: an existing label is refused, and a
failing bundle leaves nothing behind. It exits 1 on any failure.
"""

from __future__ import annotations

import argparse
import os
import hashlib
import re
import shutil
import sys
from datetime import datetime
from fnmatch import fnmatch
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
    """A submission that cannot be frozen: a missing render, an outside figure, a used label."""


# What the source snapshot leaves out of the paper's project: render outputs
# and caches at any depth, earlier bundles, and the fonts and mark that
# releases before v0.0.9 copied beside an input (format-resources) and a
# project may still hold, at the top level only, so the project's own
# figures and the installed extensions' fonts stay.
SNAPSHOT_SKIP_DIRS = {"_output", ".quarto", ".qdiff", "__pycache__", ".git", ".pixi",
                      "submission", "submissions"}
SNAPSHOT_SKIP_TOP = ("*.ttf", "*.otf", "ssus-mark-*.pdf", "ssus-mark-*.svg", "mathjax-config.js")


def snapshot(paper: Path, dest: Path, *, skip: tuple[Path, ...] = ()) -> int:
    """Copy the paper's Quarto project into ``dest`` without its render outputs.

    Skips the folders in ``SNAPSHOT_SKIP_DIRS`` and every ``*_files/`` folder
    at any depth, the format byproducts at the top level, and each path in
    ``skip``. Returns the number of files copied.
    """
    paper = paper.resolve()
    skip_set = {p.resolve() for p in skip}
    count = 0
    for d, dirs, files in os.walk(paper):
        here = Path(d)
        dirs[:] = sorted(x for x in dirs
                         if x not in SNAPSHOT_SKIP_DIRS and not x.endswith("_files")
                         and (here / x).resolve() not in skip_set)
        for name in sorted(files):
            if name == ".DS_Store":
                continue
            if here == paper and any(fnmatch(name, pat) for pat in SNAPSHOT_SKIP_TOP):
                continue
            src = here / name
            target = dest / src.relative_to(paper)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            count += 1
    return count


def stage(paper: Path, dest: Path, *, output: str = "_output", flat: bool = False) -> None:
    """Copy the upload files and the manuscript's figures into ``dest``, a new folder.

    Reads ``<output>/blind/blind.{pdf,tex}`` and
    ``<output>/titlepage/titlepage.{pdf,tex}`` in the paper's project. A
    figure resolves against the blind output folder, where Quarto copies the
    resources a render uses, and then against the project.
    """
    out = paper / output
    blind, titlepage = out / "blind", out / "titlepage"
    sources = {
        "manuscript.pdf": blind / "blind.pdf",
        "manuscript.tex": blind / "blind.tex",
        "title-page.pdf": titlepage / "titlepage.pdf",
        "title-page.tex": titlepage / "titlepage.tex",
    }
    missing = [str(p.relative_to(paper)) for p in sources.values() if not p.is_file()]
    if missing:
        raise StageError("not rendered: " + ", ".join(missing)
                         + " (render the blind and titlepage profiles first)")
    dest.mkdir(parents=True)
    for name, src in sources.items():
        shutil.copy2(src, dest / name)
    for letter in [*sorted(out.glob("*/cover_letter.pdf")), paper / "cover_letter.pdf"]:
        if letter.is_file():
            shutil.copy2(letter, dest / letter.name)
            break

    tex_path = dest / "manuscript.tex"
    tex = tex_path.read_text(encoding="utf-8")
    for p in figure_paths(tex):
        src = resolve_figure(p, blind) or resolve_figure(p, paper)
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


def tree_digest(root: Path) -> tuple[int, str]:
    """The number of files under ``root`` and one sha256 over their paths and contents."""
    h = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file())
    for p in files:
        h.update(p.relative_to(root).as_posix().encode() + b"\0")
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return len(files), h.hexdigest()


def write_manifest(dest: Path, label: str, warnings: list[str]) -> None:
    """MANIFEST.txt: the label, the checklist, each upload file's sha256, the source's digest."""
    lines = [f"submission {label} — {datetime.now():%Y-%m-%d %H:%M}",
             "checklist: ALL PASS"]
    lines += [f"  WARN  {w}" for w in warnings]
    lines.append("bundle:")
    for path in sorted(p for p in dest.rglob("*") if p.is_file()):
        rel = path.relative_to(dest)
        if rel.parts[0] in ("source", "MANIFEST.txt"):
            continue
        lines.append(f"  {hashlib.sha256(path.read_bytes()).hexdigest()}  {rel.as_posix()}")
    n, digest = tree_digest(dest / "source")
    lines += [f"source/: {n} files, tree sha256 {digest}",
              "",
              "upload: manuscript.tex (or manuscript.pdf) and each figure file;",
              "title-page.pdf in its own field; the cover letter where asked.",
              "CHECK THE TARGET JOURNAL'S INSTRUCTIONS PAGE BEFORE RELYING ON THIS BUNDLE."]
    (dest / "MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ssus_papers.submit",
        description="Freeze a submission: the upload bundle from the rendered blind manuscript "
                    "and title page, and a snapshot of the paper's source.")
    parser.add_argument("label", help="the submission's name, e.g. smr-2026-11; frozen once")
    parser.add_argument("--paper", default=".", help="the paper's Quarto project (default: .)")
    parser.add_argument("--into", default="submissions",
                        help="the folder that keeps every submission (default: submissions)")
    parser.add_argument("--output", default="_output",
                        help="the project's output folder, holding blind/ and titlepage/ (default: _output)")
    parser.add_argument("--flat", action="store_true",
                        help="bare figure filenames, for portals with a flat build directory (ScholarOne)")
    args = parser.parse_args(argv)

    paper, into = Path(args.paper), Path(args.into)
    config = paper / "_quarto.yml"
    if not config.is_file():
        print(f"FAIL  no _quarto.yml in {paper}: --paper names the paper's Quarto project")
        return 1
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.label):
        print("FAIL  a label takes letters, digits, '.', '_', and '-', and starts with a letter or digit")
        return 1
    dest = into / args.label
    if dest.exists():
        print(f"FAIL  {dest} exists: a submission is frozen once; choose another label")
        return 1
    partial = into / f".{args.label}.partial"
    shutil.rmtree(partial, ignore_errors=True)
    try:
        stage(paper, partial, output=args.output, flat=args.flat)
        failures, warnings = check(
            blind_body((partial / "manuscript.tex").read_text(encoding="utf-8")),
            (partial / "title-page.tex").read_text(encoding="utf-8"),
            identity_strings(config.read_text(encoding="utf-8")),
        )
        for f in failures:
            print(f"FAIL  {f}")
        for w in warnings:
            print(f"WARN  {w}")
        if failures:
            raise StageError("the blind-hygiene checklist failed; nothing was frozen")
        try:
            at = paper.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            at = Path(paper.resolve().name)
        n = snapshot(paper, partial / "source" / at, skip=(into,))
        write_manifest(partial, args.label, warnings)
        partial.rename(dest)
    except StageError as err:
        print(f"FAIL  {err}")
        shutil.rmtree(partial, ignore_errors=True)
        return 1
    print(f"checklist: ALL PASS; froze {dest}/ (the bundle, MANIFEST.txt, and source/, {n} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
