function Table(el)
  local columns = 0
  if el.colspecs then columns = #el.colspecs end
  local env = columns >= 6 and "ESDWideTable" or "ESDTable"
  return {
    pandoc.RawBlock("latex", "\\begin{" .. env .. "}"),
    el,
    pandoc.RawBlock("latex", "\\end{" .. env .. "}")
  }
end

