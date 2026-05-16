from app.ingestion.docling_parser import DoclingParser
import logging

logging.basicConfig(level=logging.INFO)

parser = DoclingParser()
print('Starting parser on 41-page PDF...')
try:
    # Just parse it to see if it throws bad_alloc
    res = parser.parse_pdf(r'E:\vraj\Projects\powermind\data\Document-Grounded Conversational AI using RAG (1).pdf')
    print('SUCCESS! Parsed pages:', len(res.document.pages))
except Exception as e:
    print('FAILED:', e)
