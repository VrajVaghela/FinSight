"""
FinSight AI — DoclingParser
Wraps the Docling SDK to convert PDF files into structured DoclingDocument objects.
Handles DocLayNet layout analysis + TableFormer table extraction.
"""
import os
# Disable HuggingFace symlinks on Windows to prevent WinError 1314
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

from pathlib import Path
from typing import Optional


class DoclingParser:
    """
    Parses a PDF using the Docling SDK.
    - DocLayNet for layout detection (headings, paragraphs, tables, figures)
    - TableFormer for table cell extraction (97.9% accuracy)
    
    Returns: A DoclingDocument object with the full element tree.
    """

    def __init__(self):
        self._converter = None

    def _get_converter(self):
        """Lazy-load DocumentConverter to avoid import-time model downloads."""
        if self._converter is None:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions
            from docling.datamodel.base_models import InputFormat

            print("[DoclingParser] Initializing DocumentConverter with memory constraints...")
            
            opts = PdfPipelineOptions()
            # Constrain ONNX runtime to prevent std::bad_alloc on large documents (e.g. 40+ pages)
            opts.accelerator_options = AcceleratorOptions(num_threads=1, device="cpu")
            opts.ocr_batch_size = 1
            opts.layout_batch_size = 1
            opts.table_batch_size = 1
            opts.do_ocr = False # Disable OCR to save memory if PDF is already searchable
            opts.generate_page_images = False
            opts.generate_picture_images = False
            opts.images_scale = 1.0

            self._converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
            )
            print("[DoclingParser] DocumentConverter ready.")
        return self._converter

    def parse_pdf(self, file_path: str, use_docling: bool = False):
        """
        Parse a PDF file.
        Now defaults to PyMuPDF (fitz) for stability and speed.
        Use Docling only for smaller or complex layout-critical files.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"PDF not found at: {path}")

        # Check if we should use Docling (default to False to prevent hangs)
        if use_docling:
            try:
                converter = self._get_converter()
                result = converter.convert(str(path))
                print(f"[DoclingParser] Successfully parsed with Docling: {path.name}")
                return result
            except Exception as e:
                print(f"[DoclingParser] WARNING: Docling failed ({e}). Falling back to PyMuPDF...")
        
        # Default to stable PyMuPDF
        return self._fallback_parse_fitz(path)


    def _fallback_parse_fitz(self, path: Path):
        """
        Fallback parser using PyMuPDF (fitz) for searchable PDFs.
        Produces one mock SectionHeaderItem per page + text items,
        so the StructuralChunker correctly splits by page.
        """
        import fitz
        
        doc = fitz.open(str(path))
        mock_items = []
        page_count = len(doc)
        
        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1
            page_width = page.rect.width
            page_height = page.rect.height
            
            # Insert a section header for each page so the chunker splits properly
            mock_items.append(MockDoclingItem(
                text=f"Page {page_num}",
                page_no=page_num,
                bbox={"l": 0, "t": 0, "r": page_width, "b": 20},
                page_width=page_width,
                page_height=page_height,
                item_type="SectionHeaderItem"
            ))
            
            # Extract text blocks for the page
            blocks = page.get_text("blocks")
            for b in blocks:
                # b = (x0, y0, x1, y1, text, block_no, block_type)
                # block_type: 0 = text, 1 = image
                if b[6] != 0:  # skip image blocks
                    continue
                text = b[4].strip()
                if not text:
                    continue
                
                mock_items.append(MockDoclingItem(
                    text=text,
                    page_no=page_num,
                    bbox={"l": b[0], "t": b[1], "r": b[2], "b": b[3]},
                    page_width=page_width,
                    page_height=page_height,
                    item_type="TextItem"
                ))
        
        doc.close()
        print(f"[DoclingParser] PyMuPDF extraction: {len(mock_items)} items from {page_count} pages.")
        return MockDoclingResult(mock_items, page_count)



class MockDoclingItem:
    def __init__(self, text, page_no, bbox, page_width, page_height, item_type="TextItem"):
        self.text = text
        self.prov = [MockProv(page_no, bbox, page_width, page_height)]
        self._item_type = item_type
        
    def export_to_markdown(self, **kwargs):
        return self.text

class MockProv:
    def __init__(self, page_no, bbox, page_width, page_height):
        self.page_no = page_no
        self.bbox = MockBBox(bbox)
        self.page_width = page_width
        self.page_height = page_height

class MockBBox:
    def __init__(self, bbox_dict):
        self.l = bbox_dict["l"]
        self.t = bbox_dict["t"]
        self.r = bbox_dict["r"]
        self.b = bbox_dict["b"]
        self.coord_origin = 0

class MockDoclingResult:
    def __init__(self, items, page_count=None):
        self.document = MockDocument(items, page_count)

class MockDocument:
    def __init__(self, items, page_count=None):
        self.items = items
        if page_count:
            self.pages = {i: {} for i in range(1, page_count + 1)}
        else:
            max_page = max([it.prov[0].page_no for it in items]) if items else 1
            self.pages = {i: {} for i in range(1, max_page + 1)}

    def iterate_items(self):
        for item in self.items:
            yield item, 0  # level 0


