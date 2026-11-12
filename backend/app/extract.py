
"""Extract structured guidance from expert-uploaded files → draft procedures only."""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

SECTION_HEADERS = {
    "signs": re.compile(r"(?i)^\s*(signs?|symptoms?|clinical\s*signs?|what\s*you\s*see)\s*[:\-]?"),
    "prevention": re.compile(r"(?i)^\s*(prevention|preventive|control|hygiene)\s*[:\-]?"),
    "treatment": re.compile(r"(?i)^\s*(treatment|management|guidance|what\s*to\s*do|procedure|steps?|actions?)\s*[:\-]?"),
    "medication": re.compile(r"(?i)^\s*(medication|medications|medicine|medicines|drugs?|product|products|dosage|dose)\s*[:\-]?"),
    "host": re.compile(r"(?i)^\s*(host|crop|animal|livestock|species)\s*[:\-]?\s*(.+)$"),
    "condition": re.compile(r"(?i)^\s*(condition|disease|pest|parasite|problem|diagnosis)\s*[:\-]?\s*(.+)$"),
}

HOST_ALIASES = {
    "maize": ["maize", "corn", "chimanga"],
    "cassava": ["cassava", "manioc", "chinangwa"],
    "tomato": ["tomato", "tomatoes"],
    "beans": ["bean", "beans", "nyemba"],
    "groundnuts": ["groundnut", "groundnuts", "peanut", "peanuts"],
    "rice": ["rice", "mpunga"],
    "chicken": ["chicken", "chickens", "poultry", "nkhuku"],
    "goats": ["goat", "goats", "mbuzi"],
    "cattle": ["cattle", "cow", "cows", "bovine", "ng'ombe", "ngombe"],
}


def extract_text_from_bytes(filename: str, content_type: str, data: bytes) -> str:
    name = (filename or "").lower()
    ct = (content_type or "").lower()
    # Plain text
    if name.endswith(".txt") or "text/plain" in ct:
        return data.decode("utf-8", errors="ignore")
    # PDF
    if name.endswith(".pdf") or "pdf" in ct:
        try:
            from pypdf import PdfReader  # type: ignore
            import io
            reader = PdfReader(io.BytesIO(data))
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            text_joined = "\n".join(parts)
            if len(text_joined.strip()) < 80:
                # scanned PDF — best-effort OCR if dependencies present
                try:
                    from pdf2image import convert_from_bytes
                    import pytesseract
                    pages = convert_from_bytes(data, dpi=150)
                    ocr_parts = [pytesseract.image_to_string(p) for p in pages[:8]]
                    extra = "\n".join(ocr_parts)
                    if len(extra.strip()) > len(text_joined.strip()):
                        return extra
                except Exception:
                    pass
            return text_joined
        except Exception:
            try:
                # minimal PDF text scrape
                text = data.decode("latin-1", errors="ignore")
                # keep readable chunks
                return "\n".join(re.findall(r"[\x20-\x7e\n\r\t]{4,}", text))[:50000]
            except Exception:
                return ""
    # Images: try OCR when pytesseract + PIL available
    if any(name.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")) or "image/" in ct:
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(data))
            try:
                import pytesseract
                ocr = pytesseract.image_to_string(img) or ""
                if ocr.strip():
                    return f"[OCR from {filename}]\n{ocr}"
            except Exception:
                pass
            return f"[Image file: {filename}]\n"
        except Exception:
            return f"[Image file: {filename}]\n"
    # docx optional
    if name.endswith(".docx"):
        try:
            import zipfile, io
            z = zipfile.ZipFile(io.BytesIO(data))
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
            return re.sub(r"<[^>]+>", " ", xml)
        except Exception:
            return ""
    return data.decode("utf-8", errors="ignore")[:50000]


def detect_host(text: str, fallback: str) -> str:
    low = text.lower()
    for key, aliases in HOST_ALIASES.items():
        for a in aliases:
            if re.search(rf"\b{re.escape(a)}\b", low):
                return key
    return (fallback or "maize").lower()


def _lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.replace("\r", "").split("\n") if ln.strip()]


def parse_sections(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {"signs": [], "prevention": [], "treatment": [], "medication": []}
    current = "treatment"  # default bucket for bullet-like lines
    condition = ""
    host_from_text = ""
    for ln in _lines(text):
        hm = SECTION_HEADERS["host"].match(ln)
        if hm:
            host_from_text = hm.group(2).strip()
            continue
        cm = SECTION_HEADERS["condition"].match(ln)
        if cm:
            condition = cm.group(2).strip()
            continue
        moved = False
        for key in ("signs", "prevention", "treatment", "medication"):
            if SECTION_HEADERS[key].match(ln):
                current = key
                # remainder after header
                rest = SECTION_HEADERS[key].sub("", ln).strip(" :-")
                if rest:
                    sections[current].append(rest)
                moved = True
                break
        if moved:
            continue
        # bullets
        clean = re.sub(r"^[\-\*\u2022\d\.\)\s]+", "", ln).strip()
        if len(clean) < 3:
            continue
        if current in sections:
            sections[current].append(clean)
    return {
        "signs": sections["signs"][:30],
        "prevention": sections["prevention"][:30],
        "treatment": sections["treatment"][:30],
        "medication": sections.get("medication", [])[:30],
        "condition": condition,
        "host_hint": host_from_text,
    }


def build_draft_from_file(
    *,
    filename: str,
    content_type: str,
    data: bytes,
    host_key: str,
    condition_label: str,
    signs_form: str,
    notes: str,
) -> Dict[str, Any]:
    text = extract_text_from_bytes(filename, content_type, data)
    parsed = parse_sections(text) if text.strip() else {
        "signs": [], "prevention": [], "treatment": [], "medication": [], "condition": "", "host_hint": ""
    }
    host = detect_host(text + " " + host_key + " " + (parsed.get("host_hint") or ""), host_key)
    title = condition_label or parsed.get("condition") or Path_stem(filename) or "Imported guidance"
    signs = list(parsed.get("signs") or [])
    if signs_form:
        signs = list(dict.fromkeys(signs + [s.strip() for s in re.split(r"[,;\n]", signs_form) if s.strip()]))
    steps = list(parsed.get("treatment") or [])
    prevention = list(parsed.get("prevention") or [])
    # If document has no clear "treatment" header, use remaining factual lines FROM THE FILE
    # (still the expert document — not model-invented medicine names).
    if not steps and text.strip():
        body_lines = []
        for ln in text.splitlines():
            ln = ln.strip()
            if len(ln) < 8:
                continue
            low = ln.lower()
            if any(h.search(ln) for h in SECTION_HEADERS.values() if h != SECTION_HEADERS.get("treatment")):
                continue
            if low.startswith("[image"):
                continue
            clean = re.sub(r"^[\-\*•\d\.\)\s]+", "", ln).strip()
            if len(clean) >= 8:
                body_lines.append(clean)
        # Prefer lines that look like guidance actions
        actionish = [b for b in body_lines if re.search(
            r"(?i)(remove|isolate|wash|clean|apply|avoid|do not|don't|refer|contact|wear|keep|monitor|check|burn|bury|report)",
            b,
        )]
        steps = (actionish or body_lines)[:40]
    if not steps:
        steps = [
            "Expert review required: open this draft, verify safe steps from the source file, then Publish.",
        ]
    # Attach signs into prevention as "Sign: ..." for ranking
    for s in signs:
        tag = f"Sign: {s}"
        if tag not in prevention:
            prevention.append(tag)
    if notes:
        prevention.append(f"Expert note: {notes[:300]}")
    meds = list(parsed.get("medication") or [])
    products = [{"name": m[:120], "note": "From source file (expert must verify before Publish)"} for m in meds[:20]]
    return {
        "host_key": host,
        "title": {"en": str(title)[:200]},
        "steps": {"en": steps[:40]},
        "prevention_steps": {"en": prevention[:50]},
        "products": products,
        "source_filename": filename,
        "extraction_notes": notes or "",
        "extracted_text_preview": (text or "")[:4000],
        "full_text": (text or "")[:50000],
        "needs_expert_review": True,
        "auto_extracted": True,
        "source_text_chars": len(text or ""),
    }


def Path_stem(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1]
    if "." in base:
        base = base.rsplit(".", 1)[0]
    return base.replace("_", " ").strip() or "Imported"


def split_document_by_hosts(text: str, default_host: str = "") -> list:
    """Split PDF only when there are CLEAR host section headers.

    Mere mentions of "chicken" or "cattle" inside a maize pest report must NOT
    create separate Armyworm drafts for livestock.
    """
    default_h = normalize_host_key(default_host) if default_host else ""
    if not text or not text.strip():
        return [{"host_key": default_h, "text": text or ""}]

    # Header-like lines: "GOATS", "Host: tomato", "Crop: Maize", "2. Cattle"
    header_re = re.compile(
        r"(?i)^\s*(?:\d+[.)]\s*)?(?:host|crop|animal|livestock|species)?\s*[:.\-–]?\s*"
        r"(maize|corn|tomato|tomatoes|cassava|beans?|groundnuts?|rice|chicken|chickens|poultry|"
        r"goats?|cattle|cows?|pigs?|sheep|ducks?)\s*$"
    )
    section_hosts = []
    for ln in text.splitlines():
        m = header_re.match(ln.strip())
        if not m:
            # also accept ALL-CAPS single host word lines
            raw = ln.strip()
            if raw.isupper() and 3 <= len(raw) <= 20:
                m = header_re.match(raw.title())
        if m:
            h = normalize_host_key(m.group(1) if m.lastindex else raw)
            if h and h not in section_hosts:
                section_hosts.append(h)

    # Not enough clear sections → one draft for the form host (or detected primary)
    if len(section_hosts) <= 1:
        primary = section_hosts[0] if section_hosts else default_h
        if not primary:
            primary = detect_host(text, default_h) if default_h or text else default_h
        return [{"host_key": primary or default_h or "unknown", "text": text}]

    # Split only on real headers
    chunks = {h: [] for h in section_hosts}
    current = section_hosts[0]
    for ln in text.splitlines():
        m = header_re.match(ln.strip())
        if m:
            h = normalize_host_key(m.group(1))
            if h in chunks:
                current = h
        chunks.setdefault(current, []).append(ln)

    out = []
    for h, lines in chunks.items():
        body = "\n".join(lines).strip()
        # require substantial body so tiny TOC mentions do not become drafts
        if len(body) > 120:
            out.append({"host_key": h, "text": body})
    if len(out) <= 1:
        primary = out[0]["host_key"] if out else (default_h or section_hosts[0])
        return [{"host_key": primary, "text": text}]
    return out


def normalize_host_key(host_key: str) -> str:
    h = (host_key or "").lower().strip().replace("-", "_").replace(" ", "_")
    for canon, aliases in HOST_ALIASES.items():
        if h == canon or h in aliases or h.rstrip("s") in aliases:
            return canon
    return h
