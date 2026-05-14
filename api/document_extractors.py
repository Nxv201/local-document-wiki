"""
document_extractors.py — Extract Documents from PPTX and PDF files.

Strategy:
- PPTX: Fast path = python-pptx text extraction per slide.
         Vision path = render slide as PNG → qwen2.5vl:7b when slide has embedded images.
- PDF:  Fast path = PyMuPDF text extraction per page.
         Vision path = render page as PNG → qwen2.5vl:7b for scanned/image-heavy pages.

Each slide/page becomes one Document with rich metadata.
"""
import io
import logging
import os
from pathlib import Path
from typing import List

from adalflow.core.types import Document

logger = logging.getLogger(__name__)

# Minimum character count below which we consider a slide/page "visually dominant"
# and fall through to Vision LLM extraction
_MIN_TEXT_CHARS = 50


# ---------------------------------------------------------------------------
# PPTX Extractor
# ---------------------------------------------------------------------------

class PptxExtractor:
    """Extract Documents from PowerPoint (.pptx/.ppt) files.

    Processing per slide:
    1. Extract all text shapes via python-pptx (fast, no network).
    2. If the text is sparse (< _MIN_TEXT_CHARS chars) OR the slide has picture
       shapes that cannot be described by text alone, render the slide to a PNG
       image and call the Vision LLM to describe it.
    3. Merge both extractions (text + vision description) into one Document.
    """

    def extract(self, file_path: str) -> List[Document]:
        """
        Extract Documents from a PPTX file.

        Args:
            file_path: Absolute path to the .pptx file.

        Returns:
            List of Document objects, one per slide.
        """
        try:
            from pptx import Presentation
            from pptx.util import Inches
        except ImportError:
            logger.error("python-pptx is not installed. Run: pip install python-pptx")
            return []

        documents: List[Document] = []
        rel_path = file_path  # keep full path for metadata; caller can make relative

        try:
            prs = Presentation(file_path)
        except Exception as e:
            logger.error(f"Failed to open PPTX file {file_path}: {e}")
            return []

        total_slides = len(prs.slides)
        logger.info(f"Processing PPTX: {file_path} ({total_slides} slides)")

        for slide_idx, slide in enumerate(prs.slides, start=1):
            slide_text = self._extract_slide_text(slide)
            has_images = self._slide_has_images(slide)

            vision_text = ""
            use_vision = has_images or len(slide_text.strip()) < _MIN_TEXT_CHARS

            if use_vision:
                logger.debug(f"Slide {slide_idx}: using Vision LLM (has_images={has_images}, text_len={len(slide_text)})")
                image_bytes = self._render_slide_to_png(slide, prs)
                if image_bytes:
                    from api.vision_client import extract_image_content
                    vision_text = extract_image_content(image_bytes)
                    if vision_text:
                        logger.debug(f"Slide {slide_idx}: Vision extracted {len(vision_text)} chars")
                    else:
                        logger.warning(f"Slide {slide_idx}: Vision extraction returned empty result")

            # Combine text sources — prefer vision output when available, append raw text as supplement
            if vision_text:
                combined_text = vision_text
                if slide_text.strip():
                    combined_text += f"\n\n---\n**Raw text extracted:**\n{slide_text}"
            else:
                combined_text = slide_text

            if not combined_text.strip():
                logger.debug(f"Slide {slide_idx}: skipping — no content extracted")
                continue

            # Build slide title from the first text frame that looks like a title
            slide_title = self._get_slide_title(slide) or f"Slide {slide_idx}"

            doc = Document(
                text=combined_text,
                meta_data={
                    "file_path": rel_path,
                    "slide_number": slide_idx,
                    "slide_title": slide_title,
                    "total_slides": total_slides,
                    "source_type": "pptx",
                    "title": f"{Path(file_path).stem} — {slide_title} (slide {slide_idx}/{total_slides})",
                    "type": "pptx",
                    "is_code": False,
                    "is_implementation": False,
                    "token_count": len(combined_text.split()),
                    "used_vision": bool(vision_text),
                },
            )
            documents.append(doc)

        logger.info(f"PPTX extraction complete: {len(documents)}/{total_slides} slides extracted from {file_path}")
        return documents

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_slide_text(self, slide) -> str:
        """Extract all visible text from a slide using python-pptx."""
        lines = []
        try:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            lines.append(text)
                # Also capture table cell text
                if shape.has_table:
                    for row in shape.table.rows:
                        row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_texts:
                            lines.append(" | ".join(row_texts))
        except Exception as e:
            logger.warning(f"Error extracting text from slide: {e}")
        return "\n".join(lines)

    def _slide_has_images(self, slide) -> bool:
        """Return True if the slide contains any picture shapes."""
        try:
            from pptx.enum.shapes import MSO_SHAPE_TYPE
            for shape in slide.shapes:
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    return True
                # Check for group shapes that might contain images
                if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                    return True  # conservative — groups might contain images
        except Exception as e:
            logger.warning(f"Error checking for images in slide: {e}")
        return False

    def _get_slide_title(self, slide) -> str:
        """Extract the slide title from the title placeholder, if present."""
        try:
            if slide.shapes.title and slide.shapes.title.has_text_frame:
                title = slide.shapes.title.text_frame.text.strip()
                if title:
                    return title
        except Exception:
            pass
        return ""

    def _render_slide_to_png(self, slide, presentation) -> bytes:
        """
        Render a slide to a PNG image.

        Uses python-pptx to build an EMF, then converts via Pillow.
        Falls back to a blank bytes on error.
        """
        try:
            from PIL import Image, ImageDraw
            import pptx.util as pptx_util

            # Get slide dimensions
            slide_width = presentation.slide_width
            slide_height = presentation.slide_height

            # Compute pixel dimensions at 96 dpi
            dpi = 96
            emu_per_inch = 914400
            width_px = int(slide_width / emu_per_inch * dpi)
            height_px = int(slide_height / emu_per_inch * dpi)

            # We cannot render PPTX slides natively in pure Python without LibreOffice or
            # a Windows COM automation. However, we can extract text + shapes and build
            # a representative image, OR we can use python-pptx's thumbnail if available.
            #
            # Best practical approach: extract text shapes into a simple image so the
            # Vision LLM gets something useful.
            img = Image.new("RGB", (width_px, height_px), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)

            y_pos = 10
            scale_x = width_px / slide_width
            scale_y = height_px / slide_height

            for shape in slide.shapes:
                if shape.has_text_frame:
                    x = int(shape.left * scale_x)
                    y = int(shape.top * scale_y)
                    text = shape.text_frame.text.strip()
                    if text:
                        draw.text((x, y), text[:200], fill=(0, 0, 0))

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        except ImportError:
            logger.warning("Pillow not installed — cannot render slide to PNG")
            return b""
        except Exception as e:
            logger.warning(f"Error rendering slide to PNG: {e}")
            return b""


# ---------------------------------------------------------------------------
# PDF Extractor
# ---------------------------------------------------------------------------

class PdfExtractor:
    """Extract Documents from PDF files using PyMuPDF.

    Processing per page:
    1. Try digital text extraction with fitz.Page.get_text() (fast path).
    2. If text is sparse (< _MIN_TEXT_CHARS), render the page as a PNG image
       and call Vision LLM to extract content from the scan.
    """

    def extract(self, file_path: str) -> List[Document]:
        """
        Extract Documents from a PDF file.

        Args:
            file_path: Absolute path to the .pdf file.

        Returns:
            List of Document objects, one per page.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF is not installed. Run: pip install PyMuPDF")
            return []

        documents: List[Document] = []
        rel_path = file_path

        try:
            pdf = fitz.open(file_path)
        except Exception as e:
            logger.error(f"Failed to open PDF file {file_path}: {e}")
            return []

        total_pages = len(pdf)
        logger.info(f"Processing PDF: {file_path} ({total_pages} pages)")

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            try:
                page = pdf[page_idx]
                page_text = page.get_text("text").strip()

                vision_text = ""
                use_vision = len(page_text) < _MIN_TEXT_CHARS

                if use_vision:
                    logger.debug(f"Page {page_num}: using Vision LLM (text_len={len(page_text)})")
                    image_bytes = self._render_page_to_png(page)
                    if image_bytes:
                        from api.vision_client import extract_image_content
                        vision_text = extract_image_content(image_bytes)
                        if vision_text:
                            logger.debug(f"Page {page_num}: Vision extracted {len(vision_text)} chars")
                        else:
                            logger.warning(f"Page {page_num}: Vision extraction returned empty result")

                # Combine sources
                if vision_text:
                    combined_text = vision_text
                    if page_text:
                        combined_text += f"\n\n---\n**Raw text extracted:**\n{page_text}"
                else:
                    combined_text = page_text

                if not combined_text.strip():
                    logger.debug(f"Page {page_num}: skipping — no content extracted")
                    continue

                doc = Document(
                    text=combined_text,
                    meta_data={
                        "file_path": rel_path,
                        "page_number": page_num,
                        "total_pages": total_pages,
                        "source_type": "pdf",
                        "title": f"{Path(file_path).stem} — Page {page_num}/{total_pages}",
                        "type": "pdf",
                        "is_code": False,
                        "is_implementation": False,
                        "token_count": len(combined_text.split()),
                        "used_vision": bool(vision_text),
                    },
                )
                documents.append(doc)

            except Exception as e:
                logger.error(f"Error processing PDF page {page_num} in {file_path}: {e}")
                continue

        pdf.close()
        logger.info(f"PDF extraction complete: {len(documents)}/{total_pages} pages extracted from {file_path}")
        return documents

    def _render_page_to_png(self, page, dpi: int = 150) -> bytes:
        """Render a PDF page to a PNG image at the given DPI."""
        try:
            import fitz
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            return pix.tobytes("png")
        except Exception as e:
            logger.warning(f"Error rendering PDF page to PNG: {e}")
            return b""


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def extract_documents_from_file(file_path: str) -> List[Document]:
    """
    Route a file to the appropriate extractor based on its extension.

    Args:
        file_path: Absolute path to the document file.

    Returns:
        List of Document objects extracted from the file. Empty list on error or unsupported type.
    """
    ext = Path(file_path).suffix.lower()

    if ext in (".pptx", ".ppt"):
        return PptxExtractor().extract(file_path)
    elif ext == ".pdf":
        return PdfExtractor().extract(file_path)
    else:
        logger.warning(f"extract_documents_from_file: unsupported file type '{ext}' for {file_path}")
        return []
