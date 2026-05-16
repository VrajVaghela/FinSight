from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.backend.pymupdf_backend import PyMuPdfDocumentBackend
import logging

logging.basicConfig(level=logging.INFO)

opts = PdfPipelineOptions()
opts.accelerator_options = AcceleratorOptions(num_threads=1, device="cpu")

# Set backend to pymupdf
converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts, backend=PyMuPdfDocumentBackend)}
)

print('Starting parser on 41-page PDF using PyMuPdf backend...')
try:
    res = converter.convert(r'E:\vraj\Projects\powermind\data\Document-Grounded Conversational AI using RAG (1).pdf')
    print('SUCCESS! Parsed pages:', len(res.document.pages))
except Exception as e:
    print('FAILED:', e)
