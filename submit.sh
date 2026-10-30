#!/usr/bin/env bash
# submit.sh — build the submission bundle: blind manuscript + title page.
#
#   ./submit.sh [MANUSCRIPT]
#
# MANUSCRIPT defaults to template.qmd (a paper renames it; pass its name).
# Stages into ./submission/ and runs the blind-hygiene checklist built from
# the real identity in _quarto-pretty.yml. Exits 1 on any leak, any compile
# failure, or an asset that resolves outside the project root.
set -uo pipefail

MANUSC="${1:-template.qmd}"
TITLEPAGE="title-page.qmd"
BUNDLE="submission"
OUT="${OUT_DIR:-}"          # set OUT_DIR= for projects with an output-dir
STEM="${MANUSC%.qmd}"

command -v quarto >/dev/null 2>&1 || { echo "FAIL: quarto not on PATH"; exit 1; }
[ -f "$MANUSC" ] || { echo "FAIL: no manuscript $MANUSC"; exit 1; }
[ -f "$TITLEPAGE" ] || { echo "FAIL: no $TITLEPAGE"; exit 1; }
[ -f "_quarto-pretty.yml" ] || { echo "FAIL: no _quarto-pretty.yml (the identity's home)"; exit 1; }

echo "== render =="
quarto render "$MANUSC" --profile blind --to ssus-blind-pdf \
  || { echo "FAIL: blind render"; exit 1; }
quarto render "$TITLEPAGE" --profile pretty --to ssus-titlepage-pdf \
  || { echo "FAIL: title-page render"; exit 1; }

echo "== stage =="
rm -rf "$BUNDLE"; mkdir -p "$BUNDLE"
# keep-tex names the .tex by the input's stem; the pdf follows the output-file
# (the blind format's default) — both may sit under $OUT when the project
# sets an output-dir.
cp "${OUT}blind.pdf" "$BUNDLE/manuscript.pdf" \
  || { echo "FAIL: no ${OUT}blind.pdf"; exit 1; }
cp "${OUT}$STEM.tex" "$BUNDLE/manuscript.tex" \
  || { echo "FAIL: no ${OUT}$STEM.tex (keep-tex must stay on)"; exit 1; }
cp "${OUT}${TITLEPAGE%.qmd}.pdf" "$BUNDLE/title-page.pdf" \
  || { echo "FAIL: no title-page pdf"; exit 1; }
cp "${OUT}${TITLEPAGE%.qmd}.tex" "$BUNDLE/title-page.tex" 2>/dev/null \
  || cp "${TITLEPAGE%.qmd}.tex" "$BUNDLE/title-page.tex"
[ -f "cover_letter.pdf" ] && cp cover_letter.pdf "$BUNDLE/"

echo "== figures (preserve the .tex's relative tree) =="
while IFS= read -r p; do
  found=""
  for cand in "$p" "$p.pdf" "$p.png" "$p.jpg" "$p.jpeg" "$p.eps"; do
    if [ -f "$cand" ]; then
      mkdir -p "$BUNDLE/$(dirname "$p")"
      cp "$cand" "$BUNDLE/$cand"
      found=1
      break
    fi
  done
  if [ -z "$found" ]; then
    echo "FAIL: figure $p resolves nowhere in-tree; move it into the project"
    exit 1
  fi
done < <(grep -oE '\\includegraphics(\[[^]]*\])?\{[^}]*\}' "$BUNDLE/manuscript.tex" \
  | sed -E 's/\\includegraphics(\[[^]]*\])?\{//; s/\}$//')
echo "figures ok"

echo "== references =="
# citeproc embeds the references in the .tex: no .bbl. A paper whose
# profile flips to a bibliographic route gets the .bib staged and the
# engine run here; either way the manifest states which branch ran.
if grep -qE '\\addbibresource|\\bibliography\{' "$BUNDLE/manuscript.tex"; then
  echo "detected a bibliographic command; staging the bib and running the engine in-bundle"
  cp *.bib "$BUNDLE/" 2>/dev/null
  ( cd "$BUNDLE" \
    && { biber manuscript >/dev/null 2>&1 || bibtex manuscript >/dev/null 2>&1; } \
    && pdflatex -interaction=nonstopmode manuscript.tex >/dev/null 2>&1 \
    && pdflatex -interaction=nonstopmode manuscript.tex >/dev/null 2>&1 ) \
    || { echo "FAIL: in-bundle bibliographic build"; exit 1; }
  cp "$BUNDLE/manuscript.bbl" "$BUNDLE/manuscript.bbl" 2>/dev/null
else
  echo "references embedded (citeproc) — no .bbl needed"
fi

echo "== Editorial-Manager parity compile =="
( cd "$BUNDLE" \
  && pdflatex -interaction=nonstopmode manuscript.tex >/dev/null 2>&1 \
  && pdflatex -interaction=nonstopmode manuscript.tex >/dev/null 2>&1 \
  && [ -s manuscript.pdf ] ) || { echo "FAIL: parity compile"; exit 1; }
echo "parity compile ok"

echo "== blind hygiene (identity read from _quarto-pretty.yml) =="
# The checklist reads a comment-stripped copy: LaTeX comments (a format's
# own provenance text) are not manuscript content and would fail every
# string check.
python3 - <<PYSUB
body = []
for line in open("$BUNDLE/manuscript.tex", encoding="utf-8", errors="ignore"):
    stripped = line.lstrip()
    if not stripped.startswith("%"):
        body.append(stripped)
open("_blind_body.tex", "w", encoding="utf-8").write("".join(body))

if any(ord(ch) > 127 for ch in "".join(body)):
    print("WARN  non-ASCII bytes in the blind manuscript body")
PYSUB
[ -s _blind_body.tex ] || { echo "FAIL: checklist prep (the strip step)"; exit 1; }
python3 - <<'PYEOF' > _identity_strings.txt
import re
t = open("_quarto-pretty.yml").read()
out = []
for m in re.findall(r"^[\s\-]*name: ([^\n]+)", t, re.M):
    s = m.strip().strip('"')
    if s and len(s) > 2:
        out.append(re.escape(s))
for m in re.findall(r"^[\s\-]*email: ([^\n]+)", t, re.M):
    s = m.strip().strip('"').split("@")[0].strip()
    if s and len(s) > 2:
        out.append(re.escape(s))
for line in out:
    print(line)
PYEOF

problems=0
while IFS= read -r s; do
  grep -q "$s" _blind_body.tex \
    && { echo "FAIL  $s appears in the blind manuscript"; problems=1; }
  grep -q "$s" "$BUNDLE/title-page.tex" \
    || echo "WARN  $s not found in the title page (check its block)"
done < _identity_strings.txt

for pat in '\\thanks\{' '[Aa]cknowledg' '[Ww]e thank' '[Ww]e are grateful' \
           '[Ff]unded by' '[Ss]upported by'; do
  grep -qE "$pat" _blind_body.tex \
    && { echo "FAIL  $pat matches the blind manuscript"; problems=1; }
done
grep -qE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' _blind_body.tex \
  && { echo "FAIL  an email-like string in the blind manuscript"; problems=1; }
grep -qE '[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]' _blind_body.tex \
  && { echo "FAIL  an ORCID-shaped string in the blind manuscript"; problems=1; }
grep -qE '\\\\set(main|sans|mono|math)font' _blind_body.tex \
  && { echo "FAIL  a fontspec font command in the blind manuscript (pdflatex cannot run it)"; problems=1; }
rm -f _identity_strings.txt _blind_body.tex
[ $problems -eq 0 ] && echo "hygiene: blind manuscript all-PASS"

echo "== manifest =="
{
  echo "submission bundle — $(date '+%Y-%m-%d %H:%M')"
  echo "commands:"
  echo "  quarto render $MANUSC --profile blind --to ssus-blind-pdf"
  echo "  quarto render $TITLEPAGE --profile pretty --to ssus-titlepage-pdf"
  echo "  pdflatex -interaction=nonstopmode manuscript.tex (x2, in-bundle parity compile)"
  [ $problems -eq 0 ] && echo "checklist: ALL PASS" || echo "checklist: FAILURES ABOVE — DO NOT SUBMIT"
  echo "files:"
  ( cd "$BUNDLE" && shasum -a 256 $(find . -type f | sort) )
  echo
  echo "upload: manuscript.tex (or manuscript.pdf) + individual figure files;"
  echo "title-page.pdf in its own field; cover letter where asked."
  echo "CHECK THE TARGET JOURNAL'S INSTRUCTIONS PAGE BEFORE RELYING ON THIS BUNDLE."
} > "$BUNDLE/MANIFEST.txt"

echo "== done =="
echo "bundle at $BUNDLE/ ; manifest: $BUNDLE/MANIFEST.txt"
exit $problems