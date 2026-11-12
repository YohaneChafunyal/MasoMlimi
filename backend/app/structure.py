"""Turn an expert file (PDF/DOCX/TXT text) into ONE DRAFT PER CONDITION with labelled sections.

Only text found under a heading in the source is stored under that heading. Unlabelled text is never
promoted to treatment or dose. The vet reviews every draft in the portal before it can be published.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

SEC_KEYS = ("signs", "symptoms", "treatment", "medication", "dose", "prevention", "refer")

# order matters: first match wins
_HEADERS: List[Tuple[str, str]] = [
    ("refer", r"when\s+to\s+(?:refer|see\s+a\s+vet|get\s+help|call\s+a\s+vet)|refer(?:ral)?|danger\s+signs?|emergency"),
    ("dose", r"dos(?:e|es|age|ages)|dosing|application\s+rates?|rates?|withdrawal(?:\s+(?:period|time))?"),
    ("medication", r"medications?|medicines?|drugs?|products?|recommended\s+products?|chemicals?|pesticides?"),
    ("symptoms", r"symptoms?"),
    ("signs", r"signs?(?:\s*(?:and|&)\s*symptoms?)?|clinical\s+signs?|what\s+you\s+see|visible\s+signs?|identification"),
    ("prevention", r"prevention|preventive|prevent|hygiene|cultural\s+control|best\s+practices?|biosecurity"),
    ("treatment", r"treatment|management|control(?:\s+measures)?|what\s+to\s+do|actions?|procedure|steps?|home\s+care"),
    ("type", r"(?:condition\s+)?type|category|classification"),
]
_HEAD_RE = [(k, re.compile(rf"^\s*(?:[#>]+\s*|[\*_]{{1,2}})?(?:\d+[.)]\s*)?(?:{p})(?:[\*_]{{1,2}})?\s*[:\-\u2013]\s*(.*)$", re.I))
            for k, p in _HEADERS]
_HEAD_ALONE = [(k, re.compile(rf"^\s*(?:[#>]+\s*|[\*_]{{1,2}})?(?:\d+[.)]\s*)?(?:{p})(?:[\*_]{{1,2}})?\s*:?\s*$", re.I))
               for k, p in _HEADERS]
_COND_RE = re.compile(r"^\s*(?:[#>]+\s*)?(?:condition|disease|pest|parasite|problem|diagnosis)\s*[:\-\u2013]\s*(.+)$", re.I)
_NUM_UNIT = re.compile(r"\d+(?:[.,]\d+)?\s*(?:ml|mg|g|kg|l|cc|%|ppm|days?|weeks?|litres?|liters?)\b|\bper\s+(?:litre|liter|animal|bird|hectare|acre)\b", re.I)
_SKIP_TITLE = re.compile(r"(?i)^(?:table of )?contents$|^index$|quick symptom lookup|sign\s*[-\u2013]\s*possible|possible (?:diseases|causes)|how to use|^part [a-z0-9]+\b|^inside this guide")
_WRAP_END = re.compile(r"^[A-Z][A-Z &/,'-]*\b(?:AND|OR|OF|FOR|TO|&)$")


def normalize_text(text: str) -> str:
    """Repair PDF artefacts: ALL-CAPS headings wrapped over two lines ('SIGNS AND' + 'SYMPTOMS'), page numbers."""
    src = [ln.rstrip() for ln in (text or "").replace("\r", "").split("\n")]
    out, i = [], 0
    while i < len(src):
        ln = src[i].strip()
        if re.fullmatch(r"(?i)(?:page\s*)?\d{1,3}(?:\s*(?:/|of)\s*\d{1,3})?", ln):
            i += 1
            continue
        if ln and _WRAP_END.match(ln):
            j = i + 1
            while j < len(src) and not src[j].strip():
                j += 1
            if j < len(src) and src[j].strip().isupper():
                out.append(ln + " " + src[j].strip())
                i = j + 1
                continue
        out.append(src[i])
        i += 1
    return "\n".join(out)


_TYPES = ("disease", "pest", "nutrient", "parasite", "deficiency", "disorder")


def header_match(line: str) -> Optional[Tuple[str, str]]:
    s = line.strip()
    if not s:
        return None
    for k, rx in _HEAD_RE:
        m = rx.match(s)
        if m:
            return k, m.group(1).strip()
    for k, rx in _HEAD_ALONE:
        if rx.match(s):
            return k, ""
    return None


def _bullet_clean(s: str) -> str:
    return re.sub(r"^\s*(?:[\-\*\u2022\u25cf]\s*)*(?:\d+[.)]\s+)?", "", s).strip()   # markers only, keep numbers


def _norm_type(v: str) -> str:
    low = v.lower()
    for t in _TYPES:
        if t in low:
            return {"deficiency": "nutrient", "disorder": "nutrient"}.get(t, t)
    return low[:30]


def parse_structured(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: [] for k in SEC_KEYS}
    out["condition_type"] = ""
    cur: Optional[str] = None
    for raw in normalize_text(text).split("\n"):
        ln = raw.strip()
        if not ln:
            continue
        hm = header_match(ln)
        if hm:
            cur, rest = hm
            if rest:
                _add(out, cur, rest)
            continue
        if cur is None:
            continue
        c = _bullet_clean(ln)
        if len(c) >= 3:
            _add(out, cur, c)
    for k in SEC_KEYS:
        out[k] = list(dict.fromkeys(out[k]))[:30]
    return out


def _add(out: dict, key: str, value: str) -> None:
    if key == "type":
        out["condition_type"] = _norm_type(value)
        return
    for part in re.split(r";\s+", value):
        part = part.strip()
        if len(part) >= 3:
            out[key].append(part)


def _title_ok(s: str) -> bool:
    return (3 <= len(s) <= 70 and not re.search(r"[.,;:!?]$", s) and not re.match(r"^[\-\*\u2022\u25cf]", s)
            and not s[0].islower())


_SUB_WORDS = {"cattle", "cow", "cows", "goat", "goats", "sheep", "pig", "pigs", "chicken", "chickens", "poultry", "duck", "ducks",
              "animals", "livestock", "crops", "crop", "humans", "people", "birds", "wild", "maize", "cassava", "tomato", "tomatoes",
              "beans", "groundnuts", "rice", "tobacco", "and", "or", "all", "other", "most", "young", "adult", "mainly", "also", "in"}


def _is_subtitle(line: str) -> bool:
    """'Cattle, sheep and goats' / '(Bacillus anthracis)' / 'Caused by a virus' are subtitles, not condition names."""
    t = line.strip()
    if re.match(r"(?i)^(also known as|caused by|affects|hosts?|species|found in|common name|scientific name|aka)\b", t):
        return True
    if t.startswith("(") and t.endswith(")"):                                    # "(Bacillus anthracis)"
        return True
    words = re.findall(r"[A-Za-z]+", t.lower())
    return bool(words) and all(w in _SUB_WORDS for w in words)


def split_conditions(text: str) -> List[Dict[str, Any]]:
    """[{title, text}]: one entry per condition heading found in the document.

    A heading is a short Title-like line followed (directly, or after ONE short subtitle line such as
    'Cattle, sheep and goats') by a section header like 'Signs:' / 'TREATMENT'."""
    lines = normalize_text(text).split("\n")
    nonempty = [i for i, l in enumerate(lines) if l.strip()]
    pos = {i: n for n, i in enumerate(nonempty)}
    heads: List[Tuple[int, str]] = []
    consumed: set = set()                      # subtitle lines already used by the title above them
    for i in nonempty:
        if i in consumed:
            continue
        s = lines[i].strip()
        m = _COND_RE.match(s)
        if m:
            heads.append((i, m.group(1).strip()))
            continue
        if header_match(s) or not _title_ok(s):
            continue
        n = pos[i]
        nxt = lines[nonempty[n + 1]] if n + 1 < len(nonempty) else ""
        subtitle_idx = None
        if not header_match(nxt):
            mid = nxt.strip()
            nxt2 = lines[nonempty[n + 2]] if n + 2 < len(nonempty) else ""
            if not (mid and len(mid) <= 90 and not re.match(r"^[\-\*\u2022\u25cf]", mid) and header_match(nxt2)
                    and _is_subtitle(mid)):
                continue
            subtitle_idx = nonempty[n + 1]
        if n > 0:
            prev = header_match(lines[nonempty[n - 1]])
            if prev and not prev[1]:           # previous header is still waiting for its content
                continue
        title = re.sub(r"^\d+[.)]\s*", "", s).strip("#*_ ")
        if not title or not title[0].isalpha() or _NUM_UNIT.search(title):
            continue                           # "5 g per animal" is a dose line, not a condition name
        heads.append((i, title))
        if subtitle_idx is not None:
            consumed.add(subtitle_idx)
    if not heads:
        return [{"title": "", "text": text or ""}]
    segs = []
    for n, (i, title) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        segs.append({"title": title, "text": "\n".join(lines[i + 1:end]).strip()})
    return segs


def _stem_name(filename: str) -> str:
    base = (filename or "").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return base.replace("_", " ").strip() or "Imported guidance"


def drafts_from_text(text: str, host_default: str, lang: str, filename: str, title_override: str = "",
                     split_hosts=None) -> List[Dict[str, Any]]:
    """Ready-to-store drafts (status is set to draft by store.add_procedure)."""
    chunks = split_hosts(text, host_default) if split_hosts else [{"host_key": host_default, "text": text}]
    drafts: List[Dict[str, Any]] = []
    n_cond = sum(len([x for x in split_conditions(c.get("text") or "") if x["title"]]) for c in chunks)
    # A book-like file (many conditions) with no clear per-animal/crop sections: the host is a GUESS.
    host_uncertain = len(chunks) == 1 and n_cond > 3
    for ch in chunks:
        host = ch.get("host_key") or host_default or "maize"
        body = ch.get("text") or ""
        segs = split_conditions(body)
        for seg in segs:
            sec = parse_structured(seg["text"])
            if not any(sec[k] for k in SEC_KEYS):
                continue
            if _SKIP_TITLE.search(seg["title"] or ""):
                continue                                  # contents / lookup tables are not conditions
            title = (title_override if (title_override and len(segs) == 1) else seg["title"]) or _stem_name(filename)
            if len(chunks) > 1 and not seg["title"]:
                title = f"{title} ({host})"
            signs_as_prev = [f"Sign: {s}" for s in sec["signs"] + sec["symptoms"]]
            drafts.append({
                "host_key": host,
                "title": {lang: title[:200]},
                "steps": {lang: sec["treatment"]},
                "prevention_steps": {lang: sec["prevention"] + signs_as_prev},
                "sections": {lang: {**{k: sec[k] for k in SEC_KEYS}, "condition_type": sec["condition_type"]}},
                "products": [{"name": m[:120], "note": "From source file (vet must verify before Publish)"}
                             for m in sec["medication"][:20]],
                "condition_type": sec["condition_type"],
                "full_text": seg["text"][:50000],
                "source_filename": filename,
                "source_lang": lang,
                "dose_verified": False,
                "dose_source": "",
                "needs_host_review": host_uncertain,
            })
    return drafts
