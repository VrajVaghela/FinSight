import sys
import glob
from pathlib import Path
import pypdfium2 as pdfium

uploads = sorted(glob.glob('backend/uploads/*.pdf'), key=lambda x: Path(x).stat().st_mtime, reverse=True)
if not uploads:
    print('No uploads found')
    sys.exit(0)

latest = uploads[0]
print(f'Checking: {latest}')
print(f'Size: {Path(latest).stat().st_size} bytes')

try:
    with open(latest, 'rb') as f:
        print(f'First 10 bytes: {f.read(10)}')
    
    doc = pdfium.PdfDocument(latest)
    print(f'Valid PDF! Pages: {len(doc)}')
except Exception as e:
    print(f'Error reading PDF: {e}')
