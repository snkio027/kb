#!/usr/bin/env python3
import sys
from pathlib import Path

import pypdfium2 as pdfium


source = Path(sys.argv[1])
output = Path(sys.argv[2])
dpi = int(sys.argv[3])
output.mkdir(parents=True, exist_ok=True)

document = pdfium.PdfDocument(source)
scale = dpi / 72
for index in range(len(document)):
    page = document[index]
    bitmap = page.render(scale=scale)
    image = bitmap.to_pil()
    image.save(output / f"page-{index + 1:02d}.png", optimize=True)
    image.close()
    bitmap.close()
    page.close()
document.close()
