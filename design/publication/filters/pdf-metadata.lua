function Pandoc(doc)
  local id = pandoc.utils.stringify(doc.meta.document_id or "")
  if id == "ESD-METHOD-001" then
    doc.meta.methodology = true
    doc.meta.cover_kicker = "NORMATIVE FOUNDATION · VOLUME I"
  else
    doc.meta.reference = true
    doc.meta.cover_kicker = "OPERATIONAL REFERENCE · VOLUME II"
  end
  return doc
end

