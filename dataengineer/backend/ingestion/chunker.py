"""
FinSight AI — StructuralChunker
Splits a DoclingDocument into heading-anchored, table-aware, image-aware chunks.
NEVER does fixed-token splits. Each table and each image is its own chunk.
"""
import os
import io
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class RawChunk:
    """A single chunk produced by the structural chunker."""
    raw_text: str                       # Original text of the chunk
    chunk_type: str                     # "text", "table", or "image"
    section_header: str = ""            # Nearest H1/H2 ancestor heading
    page_number: int = 1               # Page of first element in chunk (1-indexed)
    table_html: Optional[str] = None   # HTML serialization if chunk is a table
    image_path: Optional[str] = None   # Path to saved image file if chunk is an image
    # Bounding box data from Docling elements (collected for MetadataExtractor)
    bboxes: list = field(default_factory=list)  # list of {x, y, w, h, page} dicts


class StructuralChunker:
    """
    Walks the Docling document element tree and produces structural chunks.
    
    Rules:
    - New H1/H2 heading → start a new chunk boundary
    - Table → isolated chunk, serialized to HTML
    - Image/Figure → isolated chunk, saved to disk for Gemini Vision
    - Paragraph/list → appended to current chunk under the active heading
    - Never split a table across chunks
    """

    def __init__(self, image_output_dir: str = "./data/images"):
        self._image_dir = image_output_dir
        os.makedirs(self._image_dir, exist_ok=True)

    def chunk_document(self, docling_result, file_id: str = "") -> List[RawChunk]:
        """
        Walk the DoclingDocument and produce a list of RawChunks.
        
        Args:
            docling_result: The ConversionResult from DoclingParser.parse_pdf()
            file_id: Used to namespace saved image files
            
        Returns:
            List[RawChunk] — ordered chunks following document structure.
        """
        doc = docling_result.document
        chunks: List[RawChunk] = []
        
        current_heading = "Introduction"
        current_texts = []
        current_bboxes = []
        current_page = 1
        image_counter = 0

        # Iterate through all document items in reading order
        for item, _level in doc.iterate_items():
            item_type = type(item).__name__
            
            # Extract page number from item's provenance
            page_num = self._get_page_number(item)
            
            # Extract bounding box from item's provenance
            bbox = self._get_bounding_box(item)

            if item_type in ("SectionHeaderItem", "SectionItem"):
                # Flush current text chunk before starting new section
                if current_texts:
                    chunks.append(RawChunk(
                        raw_text="\n".join(current_texts),
                        chunk_type="text",
                        section_header=current_heading,
                        page_number=current_page,
                        bboxes=current_bboxes,
                    ))
                    current_texts = []
                    current_bboxes = []
                
                # Update the active heading
                text = self._get_text(item)
                if text.strip():
                    current_heading = text.strip()
                current_page = page_num

            elif item_type == "TableItem":
                # Flush any pending text before the table
                if current_texts:
                    chunks.append(RawChunk(
                        raw_text="\n".join(current_texts),
                        chunk_type="text",
                        section_header=current_heading,
                        page_number=current_page,
                        bboxes=current_bboxes,
                    ))
                    current_texts = []
                    current_bboxes = []

                # Table is always its own isolated chunk
                table_text = self._get_text(item)
                table_html = self._export_table_html(item, doc)
                
                table_bboxes = [bbox] if bbox else []
                chunks.append(RawChunk(
                    raw_text=table_text if table_text else "[Table]",
                    chunk_type="table",
                    section_header=current_heading,
                    page_number=page_num,
                    table_html=table_html,
                    bboxes=table_bboxes,
                ))

            elif item_type == "PictureItem":
                # Flush any pending text before the image
                if current_texts:
                    chunks.append(RawChunk(
                        raw_text="\n".join(current_texts),
                        chunk_type="text",
                        section_header=current_heading,
                        page_number=current_page,
                        bboxes=current_bboxes,
                    ))
                    current_texts = []
                    current_bboxes = []

                # Image/Figure/Chart → isolated chunk
                image_counter += 1
                image_path = self._save_image(item, doc, file_id, image_counter)
                
                image_bboxes = [bbox] if bbox else []
                caption = self._get_text(item)
                chunks.append(RawChunk(
                    raw_text=caption if caption.strip() else f"[Figure {image_counter} on page {page_num}]",
                    chunk_type="image",
                    section_header=current_heading,
                    page_number=page_num,
                    image_path=image_path,
                    bboxes=image_bboxes,
                ))

            else:
                # TextItem, ListItem, or any other content → append to current chunk
                text = self._get_text(item)
                if text and text.strip():
                    current_texts.append(text.strip())
                    if not current_bboxes:
                        current_page = page_num
                    if bbox:
                        current_bboxes.append(bbox)

        # Flush the final chunk
        if current_texts:
            chunks.append(RawChunk(
                raw_text="\n".join(current_texts),
                chunk_type="text",
                section_header=current_heading,
                page_number=current_page,
                bboxes=current_bboxes,
            ))

        text_count = sum(1 for c in chunks if c.chunk_type == 'text')
        table_count = sum(1 for c in chunks if c.chunk_type == 'table')
        image_count = sum(1 for c in chunks if c.chunk_type == 'image')
        print(f"[StructuralChunker] Produced {len(chunks)} chunks "
              f"({table_count} tables, {image_count} images, {text_count} text)")
        return chunks

    def _save_image(self, picture_item, doc, file_id: str, index: int) -> Optional[str]:
        """
        Extract and save an image from a Docling PictureItem to disk.
        Returns the file path or None if extraction fails.
        """
        try:
            image = None
            
            # Method 1: Docling PictureItem may have .image (PIL Image)
            if hasattr(picture_item, 'image') and picture_item.image is not None:
                image = picture_item.image
            
            # Method 2: Try get_image() method
            elif hasattr(picture_item, 'get_image'):
                image = picture_item.get_image(doc)

            if image is not None:
                fname = f"{file_id}_img_{index}.png"
                fpath = os.path.join(self._image_dir, fname)
                image.save(fpath)
                print(f"[StructuralChunker] Saved image: {fname}")
                return fpath

        except Exception as e:
            print(f"[StructuralChunker] Warning: Could not extract image #{index}: {e}")
        
        return None

    def _get_text(self, item) -> str:
        """Safely extract text from a Docling item."""
        # Docling items store text in .text or export_to_markdown()
        if hasattr(item, "text"):
            return item.text or ""
        if hasattr(item, "export_to_markdown"):
            return item.export_to_markdown() or ""
        return str(item)

    def _get_page_number(self, item) -> int:
        """Extract the page number from a Docling item's provenance."""
        try:
            if hasattr(item, "prov") and item.prov:
                prov = item.prov[0] if isinstance(item.prov, list) else item.prov
                if hasattr(prov, "page_no"):
                    return prov.page_no
                if hasattr(prov, "page"):
                    return prov.page
        except (IndexError, AttributeError):
            pass
        return 1

    def _get_bounding_box(self, item) -> Optional[dict]:
        """
        Extract bounding box from a Docling item's provenance.
        Returns normalized {x, y, w, h} dict (0.0 to 1.0) or None.
        """
        try:
            if hasattr(item, "prov") and item.prov:
                prov = item.prov[0] if isinstance(item.prov, list) else item.prov
                bbox = getattr(prov, "bbox", None)
                if bbox is None:
                    return None
                
                # Docling BoundingBox has l, t, r, b (left, top, right, bottom)
                # or x, y, width, height depending on version
                if hasattr(bbox, "l"):
                    x = bbox.l
                    y = bbox.t
                    w = bbox.r - bbox.l
                    h = bbox.b - bbox.t
                elif hasattr(bbox, "x"):
                    x = bbox.x
                    y = bbox.y
                    w = bbox.width if hasattr(bbox, "width") else 0
                    h = bbox.height if hasattr(bbox, "height") else 0
                else:
                    return None

                # Get page dimensions for normalization
                page_w = getattr(prov, "page_width", None) or getattr(bbox, "coord_origin", None)
                page_h = getattr(prov, "page_height", None)

                # If we can normalize, do it. Otherwise return raw coords.
                if page_w and page_h and page_w > 0 and page_h > 0:
                    return {
                        "x": round(x / page_w, 6),
                        "y": round(y / page_h, 6),
                        "w": round(w / page_w, 6),
                        "h": round(h / page_h, 6),
                    }
                else:
                    return {"x": round(x, 2), "y": round(y, 2),
                            "w": round(w, 2), "h": round(h, 2)}
        except (IndexError, AttributeError, TypeError):
            pass
        return None

    def _export_table_html(self, table_item, doc) -> Optional[str]:
        """Export a TableItem to HTML format using Docling's built-in export."""
        try:
            if hasattr(table_item, "export_to_html"):
                return table_item.export_to_html()
            if hasattr(table_item, "export_to_dataframe"):
                df = table_item.export_to_dataframe()
                return df.to_html(index=False)
            # Fallback: build simple HTML from the table's text
            text = self._get_text(table_item)
            if text:
                return f"<table><tr><td>{text}</td></tr></table>"
        except Exception as e:
            print(f"[StructuralChunker] Warning: Could not export table to HTML: {e}")
        return None
