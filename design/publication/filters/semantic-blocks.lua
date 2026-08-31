local status = {
  PASS=true, FAIL=true, UNKNOWN=true, WAIVED=true,
  CONDITIONAL=true, GO=true, ["NO-GO"]=true
}

function Code(el)
  if el.text == "CONDITIONAL_GO" then
    return pandoc.RawInline("latex", "\\ESDStatusConditionalGo")
  end
  if el.text == "NO_GO" then
    return pandoc.RawInline("latex", "\\ESDStatusNoGo")
  end
  if status[el.text] then
    return pandoc.RawInline("latex", "\\ESDStatus{" .. el.text .. "}")
  end
  if not el.text:match("%s") and not el.text:match("[{}]") then
    return pandoc.RawInline("latex", "\\nolinkurl{" .. el.text .. "}")
  end
  return el
end

function BlockQuote(el)
  local content = pandoc.utils.stringify(el.content)
  local env = "ESDQuote"
  if content:match("不得") or content:match("风险") or content:match("警告") then
    env = "ESDWarning"
  elseif content:match("规则") or content:match("原则") or content:match("定义") then
    env = "ESDPrinciple"
  end
  local blocks = {pandoc.RawBlock("latex", "\\begin{" .. env .. "}")}
  for _, block in ipairs(el.content) do blocks[#blocks + 1] = block end
  blocks[#blocks + 1] = pandoc.RawBlock("latex", "\\end{" .. env .. "}")
  return blocks
end
