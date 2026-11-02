-- blind.lua — the blind copy omits identity at the source.
--
-- The project's config carries the real author block (the display copy and
-- the title page read it), so this render drops every identity key from the
-- document's metadata before pandoc writes the .tex. Nothing derived from
-- the block can then reach the kept source a journal's portal receives:
-- not \author, not \thanks, and not hyperref's pdfauthor, which pandoc
-- builds from `author` in a template partial no format partial can reach.
-- The partials and the header's no-op \thanks stay as backstops; submit.sh's
-- checklist is the net.

local identity = {
  "author", "authors", "by-author", "by-affiliation", "affiliations",
  "institute", "thanks", "funding", "funding-statement", "additional-info",
  "correspondence-prefix", "acknowledgments", "acknowledgements",
}

function Meta(meta)
  for _, key in ipairs(identity) do
    meta[key] = nil
  end
  return meta
end
