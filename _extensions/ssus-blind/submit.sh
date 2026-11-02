#!/usr/bin/env bash
# submit.sh — build the submission bundle: blind manuscript + title page.
#
#   _extensions/ssus-lab/ssus-blind/submit.sh [MANUSCRIPT]
#
# Run it from the project root. It ships inside the ssus-blind extension, so
# `quarto add ssus-lab/ssus_papers@<tag>` delivers it at the formats' own
# version. MANUSCRIPT defaults to template.qmd (a paper renames it; pass its
# name).
# Stages into ./submission/ and runs the blind-hygiene checklist built from
# the real identity in _quarto.yml (the single-file design; a paper that
# splits identity into its own display profile sets TITLEPAGE_PROFILE).
# Exits 1 on any leak, any compile failure, or an asset that resolves
# outside the project root. Environment overrides: OUT_DIR (project
# output-dir), PDF_NAME (the blind render's pdf, default blind.pdf),
# TEX_NAME (the keep-tex tex, default <stem>.tex), TITLEPAGE_PROFILE
# (default none: the title page renders on the base config; name the
# profile that carries the identity if the paper splits it out),
# FIGS_FLAT=1 (flatten the bundle: bare figure filenames in the tex, for
# portals whose tex build directory is flat, which ScholarOne's is).
set -uo pipefail

MANUSC="${1:-template.qmd}"
TITLEPAGE="title-page.qmd"
BUNDLE="submission"
OUT="${OUT_DIR:-}"          # set OUT_DIR= for projects with an output-dir
[ -n "$OUT" ] && [ "${OUT%/}" = "${OUT}" ] && OUT="$OUT/"
STEM="${MANUSC%.qmd}"
STEM="${STEM%.md}"          # .md inputs name their keep-tex .tex after the stem too
PDF_NAME="${PDF_NAME:-blind.pdf}"
TEX_NAME="${TEX_NAME:-$STEM.tex}"
TPROF="${TITLEPAGE_PROFILE-}"   # unset or "" = the base config
TPROFARG=""
[ -n "$TPROF" ] && TPROFARG="--profile $TPROF"

command -v quarto >/dev/null 2>&1 || { echo "FAIL: quarto not on PATH"; exit 1; }
[ -f "$MANUSC" ] || { echo "FAIL: no manuscript $MANUSC"; exit 1; }
[ -f "$TITLEPAGE" ] || { echo "FAIL: no $TITLEPAGE"; exit 1; }
[ -f "_quarto.yml" ] || { echo "FAIL: no _quarto.yml"; exit 1; }

echo "== render =="
quarto render "$MANUSC" --profile blind --to ssus-blind-pdf \
  || { echo "FAIL: blind render"; exit 1; }
quarto render "$TITLEPAGE" $TPROFARG --to ssus-titlepage-pdf \
  || { echo "FAIL: title-page render"; exit 1; }

echo "== stage == "
rm -rf "$BUNDLE"; mkdir -p "$BUNDLE"
# keep-tex names the .tex by the input's stem and drops it beside the
# input (both with and without an output-dir); the pdf follows the
# output-file, under $OUT when the project sets one.
cp "${OUT}${PDF_NAME}" "$BUNDLE/manuscript.pdf" \
  || { echo "FAIL: no ${OUT}${PDF_NAME}"; exit 1; }
cp "$TEX_NAME" "$BUNDLE/manuscript.tex" \
  || { echo "FAIL: no $TEX_NAME (keep-tex must stay on; TEX_NAME if renamed)"; exit 1; }
cp "${OUT}${TITLEPAGE%.qmd}.pdf" "$BUNDLE/title-page.pdf" \
  || { echo "FAIL: no title-page pdf"; exit 1; }
cp "${TITLEPAGE%.qmd}.tex" "$BUNDLE/title-page.tex"
[ -f "cover_letter.pdf" ] && cp cover_letter.pdf "$BUNDLE/"

echo "== portal packages (ScholarOne's scanner) =="
# The tex scanners at journal portals read \usepackage tokens without
# honoring \IfFileExists, so pandoc's two guarded optional loads read as
# required packages and get flagged [Missing] against the journal's TeX
# Live (Sociological Methods & Research's ScholarOne build, 2026-11: both).
# The footnotehyper guard stays as its own ancient fallback (footnote also
# provides the \makesavenoteenv{longtable} the template keeps); xurl only
# relaxed URL breaking and the formats load url themselves, so its guard
# goes. Warn if either name survives, meaning pandoc's template drifted
# and the patterns here need updating.
python3 - "$BUNDLE/manuscript.tex" "$BUNDLE/title-page.tex" <<'PYSTRIP'
import re, sys
FOOT = re.compile(
    r"^\\IfFileExists\{footnotehyper\.sty\}"
    r"\{\\usepackage\{footnotehyper\}\}\{\\usepackage\{footnote\}\}\s*(?:%[^\n]*)?\n",
    re.M,
)
XURL = re.compile(
    r"^\s*\\IfFileExists\{xurl\.sty\}\{\\usepackage\{xurl\}\}\{\}\s*(?:%[^\n]*)?\n",
    re.M,
)
for p in sys.argv[1:]:
    try:
        s = open(p).read()
    except OSError:
        continue
    orig = s
    s = FOOT.sub(r"\\usepackage{footnote}\n", s)
    s = XURL.sub("", s)
    if re.search(r"footnotehyper|xurl", s) is not None:
        print(f"WARN  {p}: footnotehyper/xurl still mentioned after the strip "
              "(pandoc template drift - update submit.sh's strip patterns)")
    elif s != orig:
        print(f"stripped the portal-unfriendly guards from {p}")
    if s != orig:
        open(p, "w").write(s)
PYSTRIP

if [ "${FIGS_FLAT:-0}" = "1" ]; then
  echo "== figures (flattened for the portal's build directory) =="
  # Collect the paths from the tex as written (the loop below resolves
  # them in-tree), then rewrite the staged tex to bare filenames: the
  # portal compiles every upload in one flat directory.
  FIGPATHS="$(grep -oE '\\includegraphics(\[[^]]*\])?\{[^}]*\}' "$BUNDLE/manuscript.tex" \
    | sed -E 's/\\includegraphics(\[[^]]*\])?\{//; s/\}$//')"
  python3 - "$BUNDLE/manuscript.tex" <<'PYFLAT'
import re, sys
p = sys.argv[1]
s = open(p).read()
n = len(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{figures/", s))
s = re.sub(r"(\\includegraphics(?:\[[^\]]*\])?\{)figures/", r"\1", s)
open(p, "w").write(s)
print(f"flattened {n} figure path(s) to bare filenames")
PYFLAT
else
  echo "== figures (preserve the .tex's relative tree) =="
  FIGPATHS="$(grep -oE '\\includegraphics(\[[^]]*\])?\{[^}]*\}' "$BUNDLE/manuscript.tex" \
    | sed -E 's/\\includegraphics(\[[^]]*\])?\{//; s/\}$//')"
fi
while IFS= read -r p; do
  [ -z "$p" ] && continue
  found=""
  for cand in "$p" "$p.pdf" "$p.png" "$p.jpg" "$p.jpeg" "$p.eps"; do
    if [ -f "$cand" ]; then
      tgt="$p"
      [ "${FIGS_FLAT:-0}" = "1" ] && tgt="$(basename "$p")"
      mkdir -p "$BUNDLE/$(dirname "$tgt")"
      cp "$cand" "$BUNDLE/$tgt"
      found=1
      break
    fi
  done
  if [ -z "$found" ]; then
    echo "FAIL: figure $p resolves nowhere in-tree; move it into the project"
    exit 1
  fi
done <<< "$FIGPATHS"
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

echo "== blind hygiene (identity read from _quarto.yml) =="
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

text = "".join(body)
# Cut at the reference list, which keeps self-citations real, and look for
# it only after begin-document: pandoc's preamble defines the CSLReferences
# environment, and cutting at that definition left the whole body
# unchecked (kindex's SMR bundle, 2026-11-01). chr(92) is the backslash,
# kept out of this unquoted heredoc.
bs = chr(92)
start = max(text.find(bs + "begin{document}"), 0)
marks = [bs + "begin{CSLReferences}", bs + "section*{References}",
         bs + "section{References}", bs + "section*{Bibliography}",
         bs + "section{Bibliography}", bs + "bibliography{",
         bs + "printbibliography"]
cuts = [i for i in (text.find(k, start) for k in marks) if i >= 0]
if cuts:
    text = text[:min(cuts)]
open("_blind_body.tex", "w", encoding="utf-8").write(text)

if any(ord(ch) > 127 for ch in text):
    print("WARN  non-ASCII bytes in the blind manuscript body")
PYSUB
[ -s _blind_body.tex ] || { echo "FAIL: checklist prep (the strip step)"; exit 1; }
python3 - <<'PYEOF' > _identity_strings.txt
import re
t = open("_quarto.yml").read()
# each string is tagged: N = a name (both the blind body and the title page
# are checked), E = email-derived (only the blind body: only the
# corresponding author's email prints on the title page)
for m in re.findall(r"^[\s\-]*name: ([^\n]+)", t, re.M):
    s = m.strip().strip('"')
    if s and len(s) > 2:
        print("N\t" + re.escape(s))
for m in re.findall(r"^[\s\-]*email: ([^\n]+)", t, re.M):
    s = m.strip().strip('"').split("@")[0].strip()
    if s and len(s) > 2:
        print("E\t" + re.escape(s))
PYEOF

problems=0
while IFS= read -r line; do
  tag="${line%%	*}"; s="${line#*	}"
  case "$tag" in
  N|n)
    grep -q "$s" _blind_body.tex \
      && { echo "FAIL  $s appears in the blind manuscript"; problems=1; }
    grep -q "$s" "$BUNDLE/title-page.tex" \
      || echo "WARN  $s not found in the title page (check its block)"
    ;;
  *)
    grep -q "$s" _blind_body.tex \
      && { echo "FAIL  $s appears in the blind manuscript"; problems=1; }
    ;;
  esac
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
grep -qE '\\set(main|sans|mono|math)font' _blind_body.tex \
  && { echo "FAIL  a fontspec font command in the blind manuscript (pdflatex cannot run it)"; problems=1; }
rm -f _identity_strings.txt _blind_body.tex
[ $problems -eq 0 ] && echo "hygiene: blind manuscript all-PASS"

echo "== manifest =="
{
  echo "submission bundle — $(date '+%Y-%m-%d %H:%M')"
  echo "commands:"
  echo "  quarto render $MANUSC --profile blind --to ssus-blind-pdf"
  echo "  quarto render $TITLEPAGE $TPROFARG --to ssus-titlepage-pdf"
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