import os
import tempfile
from dataclasses import dataclass

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

try:
    import pytesseract
    from PIL import Image
    _TESSERACT = True
except Exception:
    _TESSERACT = False


@dataclass
class PageText:
    page: int
    text: str


@dataclass
class ExtractionResult:
    pages: list[PageText]
    used_ocr: bool
    warnings: list[str]


def extract_text(pdf_path: str, ocr_enabled: bool = True) -> ExtractionResult:
    warnings: list[str] = []
    pages: list[PageText] = []
    used_ocr = False

    if fitz is None:
        warnings.append("PyMuPDF not available; cannot extract text.")
        return ExtractionResult(pages=pages, used_ocr=False, warnings=warnings)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        warnings.append(f"Failed to open PDF: {e}")
        return ExtractionResult(pages=pages, used_ocr=False, warnings=warnings)

    total_chars = 0
    for i, page in enumerate(doc):
        try:
            txt = page.get_text() or ""
        except Exception as e:
            txt = ""
            warnings.append(f"Page {i+1} text extraction failed: {e}")
        pages.append(PageText(page=i + 1, text=txt))
        total_chars += len(txt.strip())

    # Determine if OCR needed
    avg_per_page = total_chars / max(len(pages), 1)
    needs_ocr = total_chars == 0 or avg_per_page < 40

    if needs_ocr and ocr_enabled:
        # 1) Try tesseract via pytesseract if available.
        if _TESSERACT:
            used_ocr = True
            new_pages = []
            for pt in pages:
                try:
                    page = doc[pt.page - 1]
                    pix = page.get_pixmap(dpi=200)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_txt = pytesseract.image_to_string(img)
                    if len(ocr_txt.strip()) > len(pt.text.strip()):
                        new_pages.append(PageText(page=pt.page, text=ocr_txt))
                    else:
                        new_pages.append(pt)
                except Exception as e:
                    warnings.append(f"OCR failed on page {pt.page}: {e}")
                    new_pages.append(pt)
            pages = new_pages
        else:
            # 2) Fall back to the bundled RapidOCR (ONNX) engine, which does not
            # require a system tesseract binary.
            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore
                _RAPID = True
            except Exception:
                _RAPID = False
            if _RAPID:
                try:
                    engine = RapidOCR()
                except Exception as e:
                    warnings.append(f"RapidOCR init failed: {e}")
                    engine = None
                if engine is not None:
                    used_ocr = True
                    new_pages = []
                    for pt in pages:
                        try:
                            page = doc[pt.page - 1]
                            pix = page.get_pixmap(dpi=150)
                            tmp_path = os.path.join(tempfile.gettempdir(), f"rapidocr_page_{pt.page}.png")
                            pix.save(tmp_path)
                            result, _ = engine(tmp_path)
                            try:
                                os.remove(tmp_path)
                            except OSError:
                                pass
                            if result:
                                items = []
                                for box, text, score in result:
                                    xs = [ptt[0] for ptt in box]
                                    ys = [ptt[1] for ptt in box]
                                    items.append((min(ys), min(xs), max(xs), max(ys), text))
                                mid = pix.width / 2.0

                                def column_lines(predicate):
                                    its = [it for it in items if predicate(it[1])]
                                    its.sort(key=lambda it: (it[0], it[1]))
                                    lines = []
                                    for it in its:
                                        if lines and abs(it[0] - lines[-1][0]) < 16:
                                            lines[-1][1].append(it)
                                        else:
                                            lines.append([it[0], [it]])
                                    return [" ".join(x[4] for x in ln[1]) for ln in lines]

                                left = column_lines(lambda x: x < mid)
                                right = column_lines(lambda x: x >= mid)
                                ocr_txt = "\n".join(left + [""] + right)
                                if len(ocr_txt.strip()) > len(pt.text.strip()):
                                    new_pages.append(PageText(page=pt.page, text=ocr_txt))
                                else:
                                    new_pages.append(pt)
                            else:
                                new_pages.append(pt)
                        except Exception as e:
                            warnings.append(f"RapidOCR failed on page {pt.page}: {e}")
                            new_pages.append(pt)
                    pages = new_pages
            else:
                warnings.append("OCR fallback unavailable (pytesseract and RapidOCR not installed).")
        # recompute totals after OCR
        total_chars = sum(len(p.text.strip()) for p in pages)
        if total_chars == 0:
            warnings.append("No text could be extracted from PDF (possibly scanned without OCR).")

    try:
        doc.close()
    except Exception:
        pass

    if not needs_ocr and total_chars == 0:
        warnings.append("No text extracted.")

    return ExtractionResult(pages=pages, used_ocr=used_ocr, warnings=warnings)


def extraction_to_text(result: ExtractionResult) -> str:
    parts = []
    for p in result.pages:
        parts.append(f"--- Page {p.page} ---\n{p.text}")
    return "\n\n".join(parts)
