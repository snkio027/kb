-- Presentation only: never infer requirement or verdict classes from keywords.
function Code(el)
  local escapes = {['\\']='\\textbackslash{}', ['{']='\\{', ['}']='\\}',
    ['#']='\\#', ['$']='\\$', ['%']='\\%', ['&']='\\&', ['_']='\\_',
    ['~']='\\textasciitilde{}', ['^']='\\textasciicircum{}'}
  -- A Str writer applies prose dash substitutions, which are wrong for code.
  -- Preserve every source space. seqsplit discards spaces and permits breaks
  -- inside status words; use only delimiters, spaces and long-token fallbacks.
  local pieces, run = {}, 0
  for _, cp in utf8.codes(el.text) do
    local ch = utf8.char(cp)
    if ch == ' ' then
      pieces[#pieces + 1] = '\\PreviewCodeSpace{}'
      run = 0
    else
      pieces[#pieces + 1] = escapes[ch] or ch
      run = run + 1
      if ch:match('[_/%.:=%-]') then
        pieces[#pieces + 1] = '\\allowbreak{}'
        run = 0
      elseif run >= 28 then
        -- A delimiter-free hash/identifier longer than a line remains readable.
        pieces[#pieces + 1] = '\\allowbreak{}'
        run = 0
      end
    end
  end
  local literal = table.concat(pieces)
  return pandoc.RawInline('latex', '\\PreviewInlineCode{' .. literal .. '}')
end
function CodeBlock(el)
  local env = el.attributes['preview-flow'] == 'true' and 'PreviewFlow' or 'PreviewCode'
  if el.text:find('\\end{' .. env .. '}', 1, true) then error('verbatim delimiter in source') end
  local identity = el.attributes['preview-code-id']
  if not identity or not identity:match('^[A-Z0-9-]+$') then error('missing code identity') end
  return pandoc.RawBlock('latex', '\\begin{PreviewCodeBox}{' .. identity .. '}\n\\begin{' .. env .. '}\n' .. el.text .. '\n\\end{' .. env .. '}\n\\end{PreviewCodeBox}')
end
function BlockQuote(el)
  local out = {pandoc.RawBlock('latex', '\\begin{PreviewQuote}')}
  for _, b in ipairs(el.content) do out[#out + 1] = b end
  out[#out + 1] = pandoc.RawBlock('latex', '\\end{PreviewQuote}')
  return out
end
function Table(el)
  local latex = pandoc.write(pandoc.Pandoc({el}), 'latex')
  -- Reserve the final rule's height on continuation pages as well. Otherwise
  -- longtable can move only the last-foot rule (and a repeated header) over.
  latex = latex:gsub('(\\bottomrule\\noalign{}\n)(\\endlastfoot)', '%1\\endfoot\n%1%2')
  -- Do not strand a repeated header and last-foot rule after the last data row.
  latex = latex:gsub('\\\\\n\\end{longtable}', '\\\\*\n\\end{longtable}')
  return pandoc.RawBlock('latex', '\\begin{PreviewTable}\n' .. latex .. '\n\\end{PreviewTable}')
end
function Str(el)
  if not el.text:find('/', 1, true) then return nil end
  local latex = pandoc.write(pandoc.Pandoc({pandoc.Plain({el})}), 'latex'):gsub('\n$', '')
  return pandoc.RawInline('latex', latex:gsub('/', '/\\allowbreak{}'))
end
function HorizontalRule()
  return pandoc.RawBlock('latex', '\\par\\nobreak\\vskip 5pt\\hrule height .3pt\\nobreak\\vskip 5pt')
end
function Header(el)
  local levels = {'chapter', 'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph'}
  if not el.identifier:match('^[A-Za-z0-9-]+$') then error('unsafe generated header identity') end
  local title = pandoc.write(pandoc.Pandoc({pandoc.Plain(el.content)}), 'latex'):gsub('\n$', '')
  local nav = el.attributes['preview-nav'] or levels[el.level]
  local out = ''
  if el.attributes['preview-new-page'] == 'true' then out = '\\clearpage\n' end
  if el.attributes['preview-keep'] then out = out .. '\\PreviewKeepHeadings{' .. el.attributes['preview-keep'] .. '}\n' end
  if el.attributes['preview-aliases'] then
    for alias in el.attributes['preview-aliases']:gmatch('[^,]+') do
      if not alias:match('^[A-Za-z][A-Za-z0-9-]*$') then error('unsafe source alias') end
      out = out .. '\\hypertarget{' .. alias .. '}{}'
    end
  end
  return pandoc.RawBlock('latex', out .. '\\PreviewHeading{' .. levels[el.level] .. '}{' .. nav .. '}{' .. el.identifier .. '}{' .. title .. '}')
end

-- A single reservation protects the complete adjacent heading chain and the
-- first meaningful block. It is measured with the actual fonts and linewidth.
function Pandoc(doc)
  local levels = {'chapter', 'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph'}
  local in_chain = false
  for i, block in ipairs(doc.blocks) do
    if block.t == 'Header' and not in_chain then
      local measurements = {}
      for j = i, #doc.blocks do
        local b = doc.blocks[j]
        if b.t == 'Header' then
          local title = pandoc.write(pandoc.Pandoc({pandoc.Plain(b.content)}), 'latex'):gsub('\n$', '')
          measurements[#measurements + 1] = '\\PreviewMeasureHeading{' .. levels[b.level] .. '}{' .. title .. '}'
        elseif b.t ~= 'HorizontalRule' then break end
      end
      block.attributes['preview-keep'] = table.concat(measurements)
      in_chain = true
    elseif block.t ~= 'Header' and block.t ~= 'HorizontalRule' then
      in_chain = false
    end
  end
  return doc
end

-- Apply the chain annotation before Header converts the nodes to RawBlock.
return {{Pandoc = Pandoc}, {Str = Str, Code = Code, CodeBlock = CodeBlock, BlockQuote = BlockQuote,
  Table = Table, HorizontalRule = HorizontalRule, Header = Header}}
