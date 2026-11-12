"""Text extraction for expert uploads (PDF, DOCX, TXT, image OCR) and host-section splitting.

Line breaks are preserved (headings are detected line by line in structure.py). The old extractor flattened
DOCX into one line, which made multi-condition documents impossible to split.
"""
from __future__ import annotations

import io
import re
import zipfile
from typing import Dict, List

MAX_PDF_PAGES = 200
_HOSTS = {
    "maize": ["maize", "corn"], "cassava": ["cassava"], "tomato": ["tomato", "tomatoes"], "beans": ["bean", "beans"],
    "groundnuts": ["groundnut", "groundnuts", "peanut", "peanuts"], "rice": ["rice"], "tobacco": ["tobacco"],
    "chicken": ["chicken", "chickens", "poultry"], "goats": ["goat", "goats"], "cattle": ["cattle", "cow", "cows"],
    "pigs": ["pig", "pigs"], "sheep": ["sheep"], "ducks": ["duck", "ducks"],
}
_ALIAS = {a: k for k, v in _HOSTS.items() for a in v}
_HOST_LINE = re.compile(
    r"(?i)^\s*(?:\d+[.)]\s*)?(?:host|crop|animal|livestock|species)?\s*[:.\-\u2013]?\s*("
    + "|".join(sorted(_ALIAS, key=len, reverse=True)) + r")\s*$")


def extract_text(filename: str, content_type: str, data: bytes, kind: str = "") -> str:
    name = (filename or "").lower()
    if kind == "pdf" or name.endswith(".pdf"):
        return _pdf(data)
    if kind == "docx" or name.endswith(".docx"):
        return _docx(data)
    if kind in ("png", "jpg", "webp", "gif") or (content_type or "").startswith("image/"):
        return _ocr_image(data)
    return data.decode("utf-8", errors="ignore")[:200000]


def _pdf(data: bytes) -> str:
    text = ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((pg.extract_text() or "") for pg in reader.pages[:MAX_PDF_PAGES])
    except Exception:
        text = ""
    if len(text.strip()) < 80:                     # probably scanned: OCR if available
        try:
            from pdf2image import convert_from_bytes
            import pytesseract
            pages = convert_from_bytes(data, dpi=150, first_page=1, last_page=12)
            ocr = "\n".join(pytesseract.image_to_string(p) for p in pages)
            if len(ocr.strip()) > len(text.strip()):
                return ocr
        except Exception:
            pass
    return text


def _docx(data: bytes) -> str:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        if sum(i.file_size for i in z.infolist()) > 60 * 1024 * 1024:   # zip-bomb guard
            return ""
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception:
        return ""
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'")):
        xml = xml.replace(a, b)
    return xml


def _ocr_image(data: bytes) -> str:
    try:
        from PIL import Image
        import pytesseract
        return pytesseract.image_to_string(Image.open(io.BytesIO(data))) or ""
    except Exception:
        return ""


def split_document_by_hosts(text: str, default_host: str = "") -> List[Dict[str, str]]:
    """Split only when there are CLEAR host headers (e.g. 'GOATS', 'Crop: Maize'). A passing mention
    of 'chicken' inside a maize report must not create a livestock draft."""
    default = _ALIAS.get((default_host or "").lower(), (default_host or "").lower())
    if not text or not text.strip():
        return [{"host_key": default, "text": text or ""}]
    order: List[str] = []
    first_line_of: Dict[str, int] = {}
    seen_lines = 0
    for ln in text.splitlines():
        if not ln.strip():
            continue
        seen_lines += 1
        m = _HOST_LINE.match(ln.strip())
        if m:
            h = _ALIAS[m.group(1).lower()]
            if h not in order:
                order.append(h)
                first_line_of[h] = seen_lines
    if len(order) <= 1:
        # one stray "Cattle" line deep inside a book must NOT relabel the whole book; trust it only in the title area
        if order and first_line_of[order[0]] <= 4:
            return [{"host_key": order[0], "text": text}]
        return [{"host_key": default, "text": text}]
    chunks: Dict[str, List[str]] = {h: [] for h in order}
    cur = order[0]
    for ln in text.splitlines():
        m = _HOST_LINE.match(ln.strip())
        if m:
            cur = _ALIAS[m.group(1).lower()]
            continue
        chunks[cur].append(ln)
    out = [{"host_key": h, "text": "\n".join(v).strip()} for h, v in chunks.items() if len("\n".join(v).strip()) > 120]
    return out or [{"host_key": order[0], "text": text}]
