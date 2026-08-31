local title = ""
local document_id = ""
local seen_source_title = false
local mainmatter_started = false
local appendix_started = false

local function meta_text(value)
  if not value then return "" end
  return pandoc.utils.stringify(value)
end

local function trim(s)
  return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function strip_number_prefix(inlines)
  local s = pandoc.utils.stringify(inlines)
  local stripped = s:gsub("^%d+%.%d+%.?%s*", "")
  stripped = stripped:gsub("^%d+%.%s*", "")
  if stripped == s then return inlines end
  local parsed = pandoc.read(stripped, "markdown").blocks
  if #parsed > 0 and parsed[1].content then return parsed[1].content end
  return inlines
end

local function diagram_after(label)
  local diagrams = {}
  if document_id == "ESD-METHOD-001" then
    diagrams = {
      ["完整的架构推导模型"] = "derivation-chain.tex",
      ["平面划分"] = "four-planes.tex",
      ["保证链"] = "assurance-chain.tex"
    }
  else
    diagrams = {
      ["操作模型"] = "stage-gate.tex",
      ["推荐逻辑架构"] = "can-pipeline.tex",
      ["幂等与提交协议"] = "commit-sequence.tex"
    }
  end
  local file = diagrams[label]
  if not file then return nil end
  return pandoc.RawBlock("latex", "\\input{publication/diagrams/" .. file .. "}")
end

local function normalize_header(el)
  local original = trim(pandoc.utils.stringify(el.content))
  if el.level == 1 and not seen_source_title and original == title then
    seen_source_title = true
    return {}
  end

  local is_appendix = original:match("^附录%s+[A-Z]") ~= nil
  if is_appendix then
    local stripped = original:gsub("^附录%s+[A-Z]：%s*", "")
    if stripped == original then
      stripped = original:gsub("^附录%s+[A-Z]:%s*", "")
    end
    el.content = pandoc.Inlines({pandoc.Str(stripped)})
  else
    el.content = strip_number_prefix(el.content)
  end

  local cleaned = trim(pandoc.utils.stringify(el.content))
  if cleaned == "摘要" or cleaned == "快速开始" then
    el.classes:insert("unnumbered")
  end

  local out = {}
  if el.level == 1 and not mainmatter_started then
    out[#out + 1] = pandoc.RawBlock("latex", "\\mainmatter")
    mainmatter_started = true
  end
  if is_appendix and not appendix_started then
    out[#out + 1] = pandoc.RawBlock("latex", "\\appendix")
    appendix_started = true
  end
  out[#out + 1] = el
  if cleaned == "摘要" or cleaned == "快速开始" then
    out[#out + 1] = pandoc.RawBlock("latex", "\\markboth{" .. cleaned .. "}{" .. cleaned .. "}")
  end
  local diagram = diagram_after(cleaned)
  if diagram then out[#out + 1] = diagram end
  return out
end

function HorizontalRule()
  return {}
end

function Pandoc(doc)
  title = meta_text(doc.meta.title)
  document_id = meta_text(doc.meta.document_id)
  return doc:walk({Header = normalize_header})
end
