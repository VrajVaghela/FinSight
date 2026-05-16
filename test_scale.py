from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
import logging

logging.basicConfig(level=logging.INFO)

opts = PdfPipelineOptions()
opts.accelerator_options = AcceleratorOptions(num_threads=1, device="cpu")
opts.do_ocr = False
opts.images_scale = 0.5  # Very small scale to prevent bad_alloc
opts.generate_page_images = False

converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
)

print('Starting parser with 0.5 scale...')
try:
    res = converter.convert(r'E:\vraj\Projects\powermind\data\Document-Grounded Conversational AI using RAG (1).pdf')
    print('SUCCESS! Parsed pages:', len(res.document.pages))
except Exception as e:
    print('FAILED:', e)
