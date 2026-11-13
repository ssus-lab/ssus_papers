-- masthead.lua — where the pdf's fonts and mark are installed.
--
-- The fonts and the mark stay in the extension folder; nothing is copied
-- beside the input. quarto.utils.resolve_path finds this folder at any
-- install depth (_extensions/ssus-lab/ssus-masthead/ by quarto add,
-- _extensions/ssus-masthead/ in this repo, or a parent project's
-- _extensions/), and the filter hands the paths to the preamble
-- (partials/before-title.tex) as two template variables:
--
--   ssus-masthead-fonts    the fonts folder, for fontspec's Path
--   ssus-masthead-assets   the assets folder, for the mark
--
-- Each path is relative to the input's folder, where LaTeX runs, so a kept
-- .tex names no machine's paths. Raw LaTeX inlines, so pandoc does not
-- escape the underscore in _extensions/.

local function from_input(p)
  local here = pandoc.path.directory(quarto.doc.input_file)
  if not pandoc.path.is_absolute(here) then
    here = pandoc.path.join({ pandoc.system.get_working_directory(), here })
  end
  local rel = pandoc.path.make_relative(quarto.utils.resolve_path(p), here, true)
  return (rel:gsub("\\", "/")) .. "/"
end

local function raw(s)
  return pandoc.MetaInlines({ pandoc.RawInline("latex", s) })
end

function Meta(meta)
  meta["ssus-masthead-fonts"] = raw(from_input("assets/fonts"))
  meta["ssus-masthead-assets"] = raw(from_input("assets"))
  return meta
end
