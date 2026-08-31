local function has_flow(text)
  return text:match("[│┌┐└┘├┤┬┴┼]")
      or text:match("↓")
      or text:match("→")
      or text:match("%-%>")
      or text:match("observe%s*→%s*reason")
end

function CodeBlock(el)
  local env = "ESDCode"
  for _, class in ipairs(el.classes) do
    if class == "markdown" or class == "md" then env = "ESDTemplate" end
  end
  if has_flow(el.text) then env = "ESDFlow" end
  return pandoc.RawBlock("latex", "\\begin{" .. env .. "}\n" .. el.text .. "\n\\end{" .. env .. "}")
end

