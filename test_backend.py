from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
try:
    from docling.backend.pymupdf_backend import PyMuPdfDocumentBackend
    print('PyMuPdfDocumentBackend available')
except ImportError:
    print('PyMuPdfDocumentBackend NOT available')
