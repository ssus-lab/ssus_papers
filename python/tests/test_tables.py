"""Tests for ssus_papers.tables. They need pandoc on PATH (Quarto's will do)."""

import re

import pytest

from ssus_papers import Table


def table(**kw):
    args = dict(
        label="demo",
        caption="A *demo* table, after @eq-k.",
        top=[("", 1), ("Model A", 2), ("Model B", 2)],
        header=["Region", "FE", "DID", "FE", "DID"],
        rows=[
            ["Stockton", "16.9 (4.0)", "-13.2 (7.3)", "0.529", "3,080"],
            ["Bldg $\\times$ type", "2.7 (3.8)", "-1.7 (12.7)", "0.034", "50"],
            ["San Luis Obispo", "5.8 (6.6)", "1.3 (31.4)", "0.062", "68"],
        ],
        align="lrrrr",
        groups=[2],
    )
    args.update(kw)
    return Table(**args)


def test_shape_is_checked():
    with pytest.raises(ValueError):
        table(header=["Region", "FE"])
    with pytest.raises(ValueError):
        table(top=[("", 1), ("Model A", 2)])


def test_latex():
    tex = table().to_latex()
    assert r"\multicolumn{2}{c}{Model A}" in tex
    assert r"\cmidrule(lr){2-3} \cmidrule(lr){4-5}" in tex
    assert tex.count(r"\addlinespace") == 1
    assert r"Stockton & 16.9 (4.0) & $-$13.2 (7.3) & 0.529 & 3,080 \\" in tex
    assert r"Bldg \(\times\) type" in tex
    assert tex.count(r"\endhead") == 1 and r"continued on next page" in tex
    assert not re.search(r"^\s*(& )+\\\\", tex, flags=re.M), "a row of empty cells"


def test_typst():
    typ = table().to_typst()
    assert "table.cell(colspan: 2, align: center)[Model A]" in typ
    assert "table.hline(start: 1, end: 3, stroke: 0.4pt)" in typ
    assert "table.hline(start: 3, end: 5, stroke: 0.4pt)" in typ
    assert "[−13.2~(7.3)]" in typ          # minus sign, no wrap
    assert "Bldg~$times$~type" in typ
    assert typ.count("#v(0.5em)") == 1


def test_html():
    html = table().to_html()
    assert html.count('colspan="2"') == 2
    assert "&minus;13.2 (7.3)" in html
    assert 'data-quarto-disable-processing="true"' in html
    assert html.count("padding-top: 0.7em") == 5     # one gap row, five cells


def test_quarto_include():
    q = table().to_quarto()
    assert q.startswith("::: {#tbl-demo}\n")
    for fence in ("```{=latex}", "```{=typst}", "```{=html}"):
        assert q.count(fence) == 1
    assert q.rstrip().endswith("A *demo* table, after @eq-k.\n:::")
    assert ".landscape" not in q
    assert table(landscape=True).to_quarto().startswith("::::: {.landscape}")
