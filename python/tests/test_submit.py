"""Tests for ssus_papers.submit: the pieces, then a staged bundle end to end."""

from ssus_papers import submit

PREAMBLE = (
    "\\documentclass{article}\n"
    "\\IfFileExists{footnotehyper.sty}{\\usepackage{footnotehyper}}{\\usepackage{footnote}}\n"
    "  \\IfFileExists{xurl.sty}{\\usepackage{xurl}}{} % add URL line breaks if available\n"
    "\\newenvironment{CSLReferences}{}{}\n"
)

CONFIG = """\
title: "A paper"
author:
  - name: Ada Lovelace
    email: ada@example.org
    affiliations:
      - name: Analytical Engine Society
"""


def test_strip_portal_guards():
    out, drifted = submit.strip_portal_guards(PREAMBLE)
    assert "\\usepackage{footnote}\n" in out
    assert "xurl" not in out and "footnotehyper" not in out
    assert not drifted
    _, drifted = submit.strip_portal_guards("\\usepackage{xurl}\n")
    assert drifted


def test_figure_paths_and_flatten():
    tex = ("\\includegraphics[width=1in]{figures/a.pdf}\n"
           "\\includegraphics{figures/sub/b}\n"
           "\\includegraphics{figures/a.pdf}\n")
    assert submit.figure_paths(tex) == ["figures/a.pdf", "figures/sub/b"]
    flat = submit.flatten_figures(tex)
    assert "\\includegraphics[width=1in]{a.pdf}" in flat
    assert "\\includegraphics{b}" in flat


def test_resolve_figure(tmp_path):
    root = tmp_path / "paper"
    (root / "figures").mkdir(parents=True)
    (root / "figures" / "a.png").write_bytes(b"png")
    (tmp_path / "outside.pdf").write_bytes(b"pdf")
    assert submit.resolve_figure("figures/a", root) == (root / "figures" / "a.png").resolve()
    assert submit.resolve_figure("figures/missing", root) is None
    assert submit.resolve_figure("../outside.pdf", root) is None


def test_blind_body_skips_comments_and_cuts_after_begin_document():
    tex = (PREAMBLE + "% Ada Lovelace wrote this format\n"
           "\\begin{document}\nBody text.\n"
           "\\begin{CSLReferences}{1}{0}\nLovelace, A. (1843).\n")
    body = submit.blind_body(tex)
    assert "Body text." in body
    assert "Ada Lovelace" not in body          # the comment is dropped
    assert "Lovelace, A." not in body          # cut at the list, not at the preamble's definition


def test_identity_strings():
    found = submit.identity_strings(CONFIG)
    assert ("name", "Ada Lovelace") in found
    assert ("name", "Analytical Engine Society") in found
    assert ("email", "ada") in found


def test_check():
    identity = submit.identity_strings(CONFIG)
    title_page = "Ada Lovelace, Analytical Engine Society"
    failures, warnings = submit.check("Clean body.", title_page, identity)
    assert failures == [] and warnings == []
    failures, _ = submit.check("We thank Ada Lovelace. ada@example.org 0000-0002-1825-0097",
                               title_page, identity)
    assert any("Ada Lovelace" in f for f in failures)
    assert any("we thank" in f for f in failures)
    assert any("email-like" in f for f in failures)
    assert any("ORCID" in f for f in failures)
    _, warnings = submit.check("Clean body.", "", identity)
    assert any("not found in the title page" in w for w in warnings)


def project(tmp_path, body="Clean body."):
    """A repository in the template's layout, with the blind and title-page renders done."""
    repo = tmp_path / "repo"
    paper = repo / "paper"
    blind, titlepage = paper / "_output" / "blind", paper / "_output" / "titlepage"
    for d in (paper / "figures", blind / "figures", titlepage, paper / "_extensions" / "fmt" / "fonts",
              paper / ".quarto", paper / "paper_files"):
        d.mkdir(parents=True)
    (paper / "_quarto.yml").write_text(CONFIG)
    (paper / "paper.qmd").write_text("Clean body.\n\n![A map.](figures/map.pdf)\n")
    (paper / "figures" / "map.pdf").write_bytes(b"%PDF figure")
    (paper / "_extensions" / "fmt" / "fonts" / "Face.ttf").write_bytes(b"font")
    (paper / "Face.ttf").write_bytes(b"a byproduct")
    (paper / ".quarto" / "cache").write_text("cache")
    (paper / "paper_files" / "x.js").write_text("asset")
    (blind / "figures" / "map.pdf").write_bytes(b"%PDF figure")
    (blind / "blind.pdf").write_bytes(b"%PDF blind")
    (blind / "blind.tex").write_text(
        PREAMBLE + "\\begin{document}\n" + body + "\n\\includegraphics{figures/map}\n\\end{document}\n")
    (titlepage / "titlepage.pdf").write_bytes(b"%PDF title page")
    (titlepage / "titlepage.tex").write_text("Ada Lovelace, Analytical Engine Society\n")
    return repo


def test_main_freezes_a_submission(tmp_path, monkeypatch):
    repo = project(tmp_path)
    monkeypatch.chdir(repo)
    assert submit.main(["smr-2026-11", "--paper", "paper"]) == 0
    dest = repo / "submissions" / "smr-2026-11"
    for name in ("manuscript.pdf", "manuscript.tex", "title-page.pdf", "title-page.tex",
                 "figures/map.pdf", "MANIFEST.txt"):
        assert (dest / name).is_file(), name
    assert "xurl" not in (dest / "manuscript.tex").read_text()
    manifest = (dest / "MANIFEST.txt").read_text()
    assert "checklist: ALL PASS" in manifest
    assert "figures/map.pdf" in manifest
    assert "source/: 4 files" in manifest
    source = dest / "source" / "paper"
    for name in ("paper.qmd", "_quarto.yml", "figures/map.pdf", "_extensions/fmt/fonts/Face.ttf"):
        assert (source / name).is_file(), name
    for name in ("_output", ".quarto", "paper_files", "Face.ttf"):
        assert not (source / name).exists(), name
    assert not any(p.name.endswith(".partial") for p in (repo / "submissions").iterdir())


def test_main_refuses_a_used_label(tmp_path, monkeypatch):
    repo = project(tmp_path)
    monkeypatch.chdir(repo)
    assert submit.main(["v1", "--paper", "paper"]) == 0
    manifest = (repo / "submissions" / "v1" / "MANIFEST.txt").read_text()
    assert submit.main(["v1", "--paper", "paper"]) == 1
    assert (repo / "submissions" / "v1" / "MANIFEST.txt").read_text() == manifest


def test_main_flat(tmp_path, monkeypatch):
    repo = project(tmp_path)
    monkeypatch.chdir(repo)
    assert submit.main(["v1", "--paper", "paper", "--flat"]) == 0
    dest = repo / "submissions" / "v1"
    assert (dest / "map.pdf").is_file()
    assert "\\includegraphics{map}" in (dest / "manuscript.tex").read_text()


def test_main_freezes_nothing_on_a_leak(tmp_path, monkeypatch):
    repo = project(tmp_path, body="Joint work with Ada Lovelace.")
    monkeypatch.chdir(repo)
    assert submit.main(["v1", "--paper", "paper"]) == 1
    assert not (repo / "submissions" / "v1").exists()
    assert not list((repo / "submissions").iterdir())


def test_main_fails_without_renders(tmp_path, monkeypatch):
    repo = project(tmp_path)
    (repo / "paper" / "_output" / "blind" / "blind.tex").unlink()
    monkeypatch.chdir(repo)
    assert submit.main(["v1", "--paper", "paper"]) == 1
    assert not (repo / "submissions" / "v1").exists()


def test_main_rejects_a_bad_label(tmp_path, monkeypatch):
    repo = project(tmp_path)
    monkeypatch.chdir(repo)
    assert submit.main(["../escape", "--paper", "paper"]) == 1
    assert not (repo / "submissions").exists()
