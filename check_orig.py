import pypdfium2 as pdfium
import sys

files = [
    r'E:\vraj\Projects\powermind\data\AEL Press Release Q2 FY26.pdf',
    r'E:\vraj\Projects\powermind\data\Document-Grounded Conversational AI using RAG (1).pdf'
]

for path in files:
    try:
        doc = pdfium.PdfDocument(path)
        print(f'Valid! {path} -> Pages: {len(doc)}')
    except Exception as e:
        print(f'Error reading {path}: {e}')
