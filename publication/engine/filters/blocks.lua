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
local function textext(value)
  return pandoc.write(pandoc.Pandoc({pandoc.Plain({pandoc.Str(value)})}), 'latex'):gsub('\n$', '')
end
local components = {}
local short_table_lines = 12
function CodeBlock(el)
  local env = el.attributes['preview-flow'] == 'true' and 'PreviewFlow' or 'PreviewCode'
  if el.text:find('\\end{' .. env .. '}', 1, true) then error('verbatim delimiter in source') end
  local identity = el.attributes['preview-code-id']
  if not identity or not identity:match('^[A-Z0-9-]+$') then error('missing code identity') end
  local kind = el.attributes['reading-kind'] or 'literal'
  local caption = el.attributes['reading-caption'] or ({flow='流程示意',snippet='机制片段',literal='字面文本'})[kind]
  local lines, closing = {}, 0
  for line in (el.text .. '\n'):gmatch('(.-)\n') do lines[#lines+1] = line end
  for i=#lines,1,-1 do
    if lines[i]:match('^[%s%}%]%);]*$') then closing=closing+1 else break end
  end
  local head = tonumber(el.attributes['reading-min-head']) or 4
  local tail = tonumber(el.attributes['reading-min-tail']) or 6
  local tail_start = math.max(1, #lines-math.max(tail,closing+3)+1)
  components[#components+1] = {id=identity,kind=kind,caption=caption,lines=#lines,
    closing_tail=closing,min_head_lines=head,min_tail_lines=tail,tail_start=tail_start,
    source_lines=lines,wrap=env~='PreviewFlow'}
  local out = '\\PreviewCodePolicy{'..identity..'}{'..#lines..'}{'..head..'}{'..tail_start..'}\n'
  out = out .. '\\begin{PreviewCodeBox}{' .. identity .. ' / ' .. textext(caption) .. '}{'..kind..'}\n'
  local function chunk(first,last,keep)
    if first>last then return '' end
    local part='\\begin{'..env..'}[firstnumber='..first..']\n'..table.concat(lines,'\n',first,last)..'\n\\end{'..env..'}\n'
    if keep then part='\\noindent\\begin{minipage}{\\linewidth}\n'..part..'\\end{minipage}\\par\n' end
    return part
  end
  if #lines<=16 or tail_start<=head+1 then
    out=out..chunk(1,#lines,true)
  else
    out=out..chunk(1,head,true)..chunk(head+1,tail_start-1,false)..chunk(tail_start,#lines,true)
  end
  out=out..'\\end{PreviewCodeBox}'
  return pandoc.RawBlock('latex', out)
end
function BlockQuote(el)
  local out = {pandoc.RawBlock('latex', '\\begin{PreviewQuote}')}
  for _, b in ipairs(el.content) do out[#out + 1] = b end
  out[#out + 1] = pandoc.RawBlock('latex', '\\end{PreviewQuote}')
  return out
end
function Table(el)
  local latex = pandoc.write(pandoc.Pandoc({el}), 'latex')
  local estimate = 2
  for _, body in ipairs(el.bodies) do
    for _, row in ipairs(body.body) do
      local height=1
      for i, cell in ipairs(row.cells) do
        local width = el.colspecs[i][2] or (1/#row.cells)
        local units=0
        for _, cp in utf8.codes(pandoc.utils.stringify(cell.contents)) do units=units+(cp>255 and 2 or 1) end
        height=math.max(height, math.ceil(units/math.max(12,94*width)))
      end
      estimate=estimate+height
    end
  end
  local id = el.attributes['reading-table-id'] or 'anonymous-table'
  local keep = estimate<=short_table_lines
  components[#components+1]={id=id,kind='table',estimated_lines=estimate,keep_together=keep}
  if keep then
    -- Pandoc's fixed-width columns also work in tabular. Remove only generated
    -- longtable head/foot commands, retaining every cell exactly once.
    latex=latex:gsub('\\begin{longtable}%b[]','\\begin{tabular}')
    latex=latex:gsub('\\endhead.-\\endlastfoot','')
    latex=latex:gsub('\\end{longtable}','\\bottomrule\n\\end{tabular}')
    latex='\\par\\medskip\\noindent\\begin{minipage}{\\linewidth}\n\\hypertarget{'..id..'-start}{}'..latex..'\\hypertarget{'..id..'-end}{}\n\\end{minipage}\\par\\medskip'
  else
  -- Reserve the final rule's height on continuation pages as well. Otherwise
  -- longtable can move only the last-foot rule (and a repeated header) over.
  latex = latex:gsub('(\\bottomrule\\noalign{}\n)(\\endlastfoot)', '%1\\endfoot\n%1%2')
  -- Do not strand a repeated header and last-foot rule after the last data row.
  latex = latex:gsub('\\\\\n\\end{longtable}', '\\\\*\n\\end{longtable}')
    latex='\\hypertarget{'..id..'-start}{}'..latex..'\\hypertarget{'..id..'-end}{}'
  end
  return pandoc.RawBlock('latex', '\\begin{PreviewTable}\n' .. latex .. '\n\\end{PreviewTable}')
end
function Str(el)
  if not el.text:find('/', 1, true) then return nil end
  local latex = pandoc.write(pandoc.Pandoc({pandoc.Plain({el})}), 'latex'):gsub('\n$', '')
  return pandoc.RawInline('latex', latex:gsub('/', '/\\allowbreak{}'))
end
function HorizontalRule()
  return pandoc.RawBlock('latex', '\\par\\nobreak\\vskip 4pt')
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
  local role=el.attributes['reading-role'] or levels[el.level]
  out=out .. '\\PreviewHeading{' .. role .. '}{' .. nav .. '}{' .. el.identifier .. '}{' .. title .. '}'
  if el.attributes['reading-source-note'] then
    out=out..'\n\\PreviewSourceNote{'..el.attributes['reading-source-note']..'}'
  end
  if el.attributes['reading-local-navigation'] then out=out..'\n\\PreviewLocalNavigation{}' end
  return pandoc.RawBlock('latex', out)
end

-- A single reservation protects the complete adjacent heading chain and the
-- first meaningful block. It is measured with the actual fonts and linewidth.
function Pandoc(doc)
  short_table_lines=tonumber(pandoc.utils.stringify(doc.meta.short_table_lines or '12')) or 12
  -- Group already-authored Gate number + question without rewriting either.
  local output, gate, i={},false,1
  while i<=#doc.blocks do
    local b=doc.blocks[i]
    if b.t=='Header' and b.level<=2 then
      local title=pandoc.utils.stringify(b)
      gate=title:find('Final Gate',1,true)~=nil and not title:find('参考',1,true)
    end
    local next=doc.blocks[i+1]
    if gate and b.t=='Para' and #b.content==1 and b.content[1].t=='Strong'
       and pandoc.utils.stringify(b):match('^[A-Z]%. ') then
      -- Source local labels are paragraphs, not Markdown headers. Reserve the
      -- label plus the next question's own reservation; do not change text.
      output[#output+1]=pandoc.RawBlock('latex','\\par\\Needspace{110pt}')
    end
    if gate and b.t=='Para' and pandoc.utils.stringify(b):match('^%d+$') and next and next.t=='Para' then
      local joined=b.content:clone(); joined:insert(pandoc.Space()); joined:extend(next.content)
      output[#output+1]=pandoc.RawBlock('latex','\\par\\Needspace{65pt}')
      output[#output+1]=pandoc.Para(joined); i=i+2
    else output[#output+1]=b; i=i+1 end
  end
  doc.blocks=output
  local levels = {'chapter', 'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph'}
  local in_chain = false
  for i, block in ipairs(doc.blocks) do
    if block.t == 'Header' and not in_chain then
      local measurements = {}
      for j = i, #doc.blocks do
        local b = doc.blocks[j]
        if b.t == 'Header' then
          local title = pandoc.write(pandoc.Pandoc({pandoc.Plain(b.content)}), 'latex'):gsub('\n$', '')
          measurements[#measurements + 1] = '\\PreviewMeasureHeading{' .. (b.attributes['reading-role'] or levels[b.level]) .. '}{' .. title .. '}'
          if b.attributes['reading-follow-space'] then
            measurements[#measurements+1]='\\addtolength{\\PreviewKeepHeight}{'..b.attributes['reading-follow-space']..'pt}'
          end
        elseif b.t ~= 'HorizontalRule' then
          if b.t=='Table' then
            local rows=0
            for _, body in ipairs(b.bodies) do rows=rows+#body.body end
            measurements[#measurements+1]='\\addtolength{\\PreviewKeepHeight}{'..math.min(220,(rows+3)*17)..'pt}'
          elseif b.t=='CodeBlock' then
            local _, n=b.text:gsub('\n','\n'); n=n+1
            measurements[#measurements+1]='\\addtolength{\\PreviewKeepHeight}{'..((n<=16 and n or 4)*13+32)..'pt}'
          end
          break
        end
      end
      block.attributes['preview-keep'] = table.concat(measurements)
      in_chain = true
    elseif block.t ~= 'Header' and block.t ~= 'HorizontalRule' then
      in_chain = false
    end
  end
  return doc
end

local function save_components(doc)
  local path=PANDOC_STATE.output_file:gsub('document.tex$','reading-components.json')
  local f=assert(io.open(path,'w'))
  f:write(pandoc.json.encode(components)); f:close()
  return doc
end

-- Apply the chain annotation before Header converts the nodes to RawBlock.
return {{Pandoc = Pandoc}, {Str = Str, Code = Code, CodeBlock = CodeBlock, BlockQuote = BlockQuote,
  Table = Table, HorizontalRule = HorizontalRule, Header = Header}, {Pandoc=save_components}}
