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
            from docling.document_converter import DocumentConverter
            print("[DoclingParser] Initializing DocumentConverter (first run downloads models)...")
            self._converter = DocumentConverter()
            print("[DoclingParser] DocumentConverter ready.")
        return self._converter

    def parse_pdf(self, file_path: str):
        """
        Parse a PDF file and return the Docling conversion result.
        
        Args:
            file_path: Absolute path to the PDF file.
            
        Returns:
            ConversionResult from Docling with .document (DoclingDocument).
            
        Raises:
            FileNotFoundError: If the file does not exist.
            RuntimeError: If Docling parsing fails.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"PDF not found at: {path}")

        converter = self._get_converter()
        try:
            result = converter.convert(str(path))
            print(f"[DoclingParser] Successfully parsed: {path.name}")
            return result
        except Exception as e:
            raise RuntimeError(f"Docling failed to parse '{path.name}': {e}") from e
