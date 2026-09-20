-- Presentation only: never infer requirement or verdict classes from keywords.
function Code(el)
  local escapes = {['\\']='\\textbackslash{}', ['{']='\\{', ['}']='\\}',
    ['#']='\\#', ['$']='\\$', ['%']='\\%', ['&']='\\&', ['_']='\\_',
    ['~']='\\textasciitilde{}', ['^']='\\textasciicircum{}'}
  -- A Str writer applies prose dash substitutions, which are wrong for code.
  local literal = el.text:gsub('[\\{}#$%%&_~^]', escapes)
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
  return {pandoc.RawBlock('latex', '\\begin{PreviewTable}'), el, pandoc.RawBlock('latex', '\\end{PreviewTable}')}
end
function HorizontalRule()
  return pandoc.RawBlock('latex', '\\par\\nobreak\\vskip 5pt\\hrule height .3pt\\nobreak\\vskip 5pt')
end
function Header(el)
  local levels = {'chapter', 'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph'}
  if not el.identifier:match('^[A-Za-z0-9-]+$') then error('unsafe generated header identity') end
  local title = pandoc.write(pandoc.Pandoc({pandoc.Plain(el.content)}), 'latex'):gsub('\n$', '')
  return pandoc.RawBlock('latex', '\\PreviewHeading{' .. levels[el.level] .. '}{' .. el.identifier .. '}{' .. title .. '}')
end
