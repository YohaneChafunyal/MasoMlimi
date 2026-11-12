"""MasoMlimi pilot store (JSON files, atomic writes, thread-safe).

Farmers only ever see procedures with status == "published". Doses are shown only when the publishing vet
set dose_verified + dose_source (enforced in kb_engine). Replace with PostgreSQL before production scale.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app import security

_lock = threading.RLock()
_cursor = 1
_DATA_DIR = Path(os.environ.get("MASOMLIMI_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data")))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
LIBRARY_DIR = _DATA_DIR / "library_files"
VOICE_DIR = _DATA_DIR / "voice"
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
VOICE_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, text: str) -> None:
    """Atomic write: never leaves a half-written file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default: Any, encrypted: bool = False) -> Any:
    try:
        if path.is_file():
            raw = path.read_text(encoding="utf-8")
            return json.loads(security.decrypt_blob(raw) if encrypted else raw)
    except Exception:
        pass
    return default


# ------------------------------------------------------------------------------------------------ fixed safety text
CRITICAL = {
    "en": ["Isolate the animal from other animals and people.",
           "Do not handle more than necessary. Wear gloves if available.",
           "Do not eat or sell meat, milk or eggs until a vet advises.",
           "Keep children and other animals away.",
           "Contact the nearest verified vet or district office immediately."],
    "fr": ["Isolez l'animal des autres animaux et des personnes.",
           "Ne manipulez pas plus que nécessaire. Portez des gants si possible.",
           "Ne mangez ni ne vendez viande, lait ou œufs tant qu'un vétérinaire n'a pas conseillé.",
           "Éloignez les enfants et les autres animaux.",
           "Contactez immédiatement le vétérinaire ou le bureau de district."],
    "ny": ["Patulani chiweto kuchokera ku ziweto ndi anthu ena.",
           "Osagwira kwambiri. Valani magolovesi ngati mulinawo.",
           "Osadya kapena kugulitsa nyama, mkaka kapena mazira mpaka vet atanene.",
           "Sungani ana ndi ziweto zina kutali.",
           "Lumikizanani ndi vet kapena ofesi ya boma posachedwa."],
    "sw": ["Tenganisha mnyama na wanyama na watu wengine.",
           "Usishike zaidi ya inavyohitajika. Vaa glavu ikiwa zinapatikana.",
           "Usile au uuze nyama, maziwa au mayai hadi daktari wa mifugo ashauri.",
           "Weka watoto na wanyama wengine mbali.",
           "Wasiliana na daktari wa mifugo au ofisi ya wilaya mara moja."],
    "pt": ["Isole o animal de outros animais e pessoas.",
           "Não manuseie mais do que o necessário. Use luvas se disponíveis.",
           "Não coma nem venda carne, leite ou ovos até um veterinário aconselhar.",
           "Mantenha crianças e outros animais afastados.",
           "Contacte o veterinário ou o posto distrital imediatamente."],
}


def critical_steps(lang: str) -> List[str]:
    return CRITICAL.get(lang, CRITICAL["en"])


_ALIASES = {
    "tomatoes": "tomato", "tomatoe": "tomato", "nyanya": "tomato", "tomate": "tomato",
    "corn": "maize", "chimanga": "maize", "mahindi": "maize", "milho": "maize", "mais": "maize",
    "chinangwa": "cassava", "muhogo": "cassava", "manioc": "cassava", "mandioca": "cassava",
    "bean": "beans", "nyemba": "beans", "maharagwe": "beans", "haricots": "beans",
    "groundnut": "groundnuts", "peanut": "groundnuts", "peanuts": "groundnuts", "mtedza": "groundnuts",
    "mpunga": "rice", "mchele": "rice", "riz": "rice", "arroz": "rice",
    "chickens": "chicken", "nkhuku": "chicken", "poultry": "chicken", "kuku": "chicken", "poule": "chicken", "poules": "chicken",
    "goat": "goats", "mbuzi": "goats", "chevre": "goats", "cabras": "goats",
    "cow": "cattle", "cows": "cattle", "ngombe": "cattle", "bovine": "cattle", "bovins": "cattle", "gado": "cattle",
    "pig": "pigs", "nkhumba": "pigs", "porc": "pigs",
}
_CANON = {"maize", "cassava", "tomato", "beans", "groundnuts", "rice", "chicken", "goats", "cattle", "pigs",
          "sheep", "ducks", "sorghum", "millet", "sweet_potato", "banana", "onion", "cabbage", "tobacco", "other"}


def normalize_host_key(host_key: str) -> str:
    """Exact aliases only (no fuzzy substring matching, which mislabels crops)."""
    h = re.sub(r"[\s\-]+", "_", (host_key or "").lower().strip().replace("'", ""))[:40]
    h = _ALIASES.get(h, h)
    return h


# ------------------------------------------------------------------------------------------------ procedures
PROCEDURES_FILE = _DATA_DIR / "procedures.json"
_procedures: List[Dict[str, Any]] = []


def _load_procedures() -> None:
    global _procedures, _cursor
    data = _read_json(PROCEDURES_FILE, {})
    if isinstance(data, list):
        _procedures = data
    elif isinstance(data, dict):
        _procedures = data.get("items", [])
        _cursor = int(data.get("cursor", _cursor))
    # old demo placeholder must never be served
    _procedures = [p for p in _procedures if p.get("id") != "proc-maize-demo"]
    for p in _procedures:                      # migrate data written by older versions ("Tomatoes", "maize ")
        p["host_key"] = normalize_host_key(p.get("host_key") or "")


def _save_procedures() -> None:
    _write(PROCEDURES_FILE, json.dumps({"cursor": _cursor, "items": _procedures}, ensure_ascii=False))


def content_version() -> int:
    return _cursor


def list_procedures(include_draft: bool = False) -> List[dict]:
    with _lock:
        return list(_procedures) if include_draft else [p for p in _procedures if p.get("status") == "published"]


def published_by_host() -> Dict[str, int]:
    with _lock:
        out: Dict[str, int] = {}
        for p in _procedures:
            if p.get("status") == "published":
                out[p.get("host_key") or "?"] = out.get(p.get("host_key") or "?", 0) + 1
        return out


def get_procedure(pid: str) -> Optional[dict]:
    with _lock:
        return next((p for p in _procedures if p.get("id") == pid), None)


def add_procedure(body: dict) -> dict:
    global _cursor
    with _lock:
        steps = body.get("steps") or {"en": []}
        row = {
            "id": str(uuid.uuid4()),
            "condition_id": body.get("condition_id"),
            "host_key": normalize_host_key(body.get("host_key") or ""),
            "status": "draft",
            "title": body.get("title") or {"en": "Untitled"},
            "steps": steps,
            "prevention_steps": body.get("prevention_steps") or {"en": []},
            "sections": body.get("sections") or {},
            "products": body.get("products") or [],
            "condition_type": body.get("condition_type") or "",
            "source_lang": body.get("source_lang") or next(iter(steps.keys()), "en"),
            "translation_status": body.get("translation_status") or {},
            "full_text": (body.get("full_text") or "")[:50000],
            "source_filename": (body.get("source_filename") or "")[:200],
            "needs_host_review": bool(body.get("needs_host_review")),
            "dose_verified": False,      # only publish_procedure can set these
            "dose_source": "",
            "approved_by": "",
            "approved_at": "",
            "updated_at": _now(),
        }
        _procedures.append(row)
        _cursor += 1
        _save_procedures()
        return row


_EDITABLE = {"host_key", "title", "steps", "prevention_steps", "sections", "products", "condition_type", "is_dangerous",
             "reportable", "zoonotic", "source_lang"}


def update_procedure(pid: str, fields: dict) -> Optional[dict]:
    """Vet edits a procedure. Editing a PUBLISHED one sends it back to draft (re-review required)."""
    global _cursor
    with _lock:
        p = get_procedure(pid)
        if not p:
            return None
        for k, v in fields.items():
            if k in _EDITABLE:
                p[k] = normalize_host_key(v) if k == "host_key" else v
        if "host_key" in fields:
            p["needs_host_review"] = False          # a vet saved the host: confirmed
        if p.get("status") == "published":
            p["status"] = "draft"
            p["dose_verified"], p["dose_source"] = False, ""
        p["updated_at"] = _now()
        _cursor += 1
        _save_procedures()
        return p


def publish_procedure(pid: str, approved_by: str = "", country: str = "MW", dose_verified: bool = False,
                      dose_source: str = "") -> Optional[dict]:
    global _cursor
    if not (approved_by or "").strip():
        raise ValueError("approver name is required")
    if dose_verified and not (dose_source or "").strip():
        raise ValueError("dose_source (official citation) is required to verify a dose")
    with _lock:
        p = get_procedure(pid)
        if not p:
            return None
        if p.get("needs_host_review"):
            raise ValueError("Confirm the crop/animal first: set the host key, then Save, then Publish")
        now = _now()
        p.update(status="published", updated_at=now, approved_at=now, approved_by=approved_by.strip()[:120],
                 country=(country or "MW").upper()[:2], dose_verified=bool(dose_verified),
                 dose_source=(dose_source or "").strip()[:300])
        _cursor += 1
        _save_procedures()
        return p


def set_translation(pid: str, lang: str, title: str, steps: List[str], prevention: List[str],
                    status: str = "needs_review") -> Optional[dict]:
    global _cursor
    with _lock:
        p = get_procedure(pid)
        if not p:
            return None
        p.setdefault("title", {})[lang] = title[:200]
        p.setdefault("steps", {})[lang] = steps[:60]
        p.setdefault("prevention_steps", {})[lang] = prevention[:60]
        p.setdefault("translation_status", {})[lang] = "reviewed" if status == "reviewed" else "needs_review"
        p["updated_at"] = _now()
        _cursor += 1
        _save_procedures()
        return p


def delete_procedure(pid: str) -> bool:
    global _procedures, _cursor
    with _lock:
        before = len(_procedures)
        _procedures = [p for p in _procedures if p.get("id") != pid]
        if len(_procedures) < before:
            _cursor += 1
            _save_procedures()
            return True
        return False


# ------------------------------------------------------------------------------------------------ experts
_EXPERTS_FILE = _DATA_DIR / "experts.json"
_experts: List[Dict[str, Any]] = []


def _save_experts() -> None:
    _write(_EXPERTS_FILE, json.dumps(_experts, ensure_ascii=False, indent=2))


def list_experts_for_district(district: str = "all") -> List[dict]:
    with _lock:
        active = [e for e in _experts if e.get("active", True)]
        if not district or district.lower() in ("all", "*"):
            return list(active)
        d = district.strip().lower()
        matched = [e for e in active if (e.get("district") or "").strip().lower() == d]
        return matched or list(active)


def list_experts(country: str = "MW", district: str = "Lilongwe") -> List[dict]:
    return list_experts_for_district(district or "Lilongwe")


def add_expert(body: dict) -> dict:
    global _experts, _cursor
    with _lock:
        name = (body.get("display_name") or "").strip()[:80]
        if not name:
            raise ValueError("display_name required")
        phone = body.get("phone_e164") or None
        if phone and not security.PHONE_RE.match(phone):
            raise ValueError("phone must be E.164, e.g. +265991234567")
        row = {"id": body.get("id") or str(uuid.uuid4()), "display_name": name,
               "role_label": (body.get("role_label") or "Extension officer").strip()[:60],
               "district": (body.get("district") or "Lilongwe").strip()[:60],
               "availability": body.get("availability") or "available", "phone_e164": phone,
               "supports_chat": True, "supports_voice": True, "supports_video": bool(body.get("supports_video", True)),
               "active": True}
        _experts = [e for e in _experts if e.get("id") != row["id"]]
        _experts.append(row)
        _cursor += 1
        _save_experts()
        return row


def remove_expert(eid: str) -> bool:
    global _experts
    with _lock:
        before = len(_experts)
        _experts = [e for e in _experts if e.get("id") != eid]
        if len(_experts) < before:
            _save_experts()
            return True
        return False


# ------------------------------------------------------------------------------------------------ chat (reply-to, voice)
_CHAT_FILE = _DATA_DIR / "chats.json"
_chats: Dict[str, List[Dict[str, Any]]] = {}
MAX_THREAD = 2000


def _save_chats() -> None:
    _write(_CHAT_FILE, security.encrypt_blob(json.dumps(_chats, ensure_ascii=False)))


def chat_thread_id(farmer_device_id: str, expert_id: str) -> str:
    return f"{farmer_device_id}::{expert_id}"


def list_chat(thread_id: str) -> List[dict]:
    with _lock:
        rows = list(_chats.get(thread_id, []))
    rows.sort(key=lambda m: (m.get("at") or "", m.get("id") or ""))
    return rows


def get_message(thread_id: str, msg_id: str) -> Optional[dict]:
    if not msg_id:
        return None
    with _lock:
        for m in _chats.get(thread_id, []):
            if m.get("id") == msg_id or (m.get("client_id") and m.get("client_id") == msg_id):
                return m
    return None


def _preview(m: dict) -> dict:
    text = m.get("text") or ""
    voice = m.get("type") == "audio_note" or "[voice_note:" in text or "[Voice note]" in text
    return {"id": m["id"], "sender": m.get("sender"), "type": "audio_note" if voice else m.get("type", "text"),
            "text": "" if voice else text[:140]}


def post_chat(thread_id: str, sender: str, text: str, msg_type: str = "text", client_id: Optional[str] = None,
              reply_to: Optional[str] = None) -> dict:
    with _lock:
        existing = _chats.get(thread_id, [])
        if client_id:
            for prev in existing:
                if prev.get("client_id") == client_id:
                    return prev
        if msg_type == "audio_note" and text:
            for prev in reversed(existing[-12:]):
                if prev.get("type") == "audio_note" and prev.get("text") == text:
                    return prev
        if text and existing and not client_id:
            last = existing[-1]
            if (last.get("sender") == sender and last.get("text") == text and last.get("type") == msg_type
                    and (last.get("reply_to") or "") == (reply_to or "")):
                return last
        target = get_message(thread_id, reply_to) if reply_to else None
        msg = {"id": str(uuid.uuid4()), "thread_id": thread_id, "sender": sender, "type": msg_type, "text": text,
               "client_id": client_id or "", "at": _now(),
               "reply_to": target["id"] if target else "", "reply_preview": _preview(target) if target else None}
        _chats.setdefault(thread_id, []).append(msg)
        if len(_chats[thread_id]) > MAX_THREAD:
            _chats[thread_id] = _chats[thread_id][-MAX_THREAD:]
        _save_chats()
        return msg


def list_chat_threads() -> List[dict]:
    with _lock:
        out = []
        for tid, msgs in _chats.items():
            device_id, _, expert_id = tid.partition("::")
            out.append({"thread_id": tid, "device_id": device_id, "expert_id": expert_id,
                        "message_count": len(msgs), "last_message": msgs[-1] if msgs else None})
    out.sort(key=lambda x: (x.get("last_message") or {}).get("at") or "", reverse=True)
    return out


def delete_device_chats(device_id: str) -> int:
    """'Delete my data'."""
    with _lock:
        gone = [t for t in _chats if t.startswith(device_id + "::")]
        for t in gone:
            del _chats[t]
        if gone:
            _save_chats()
        return len(gone)


# ------------------------------------------------------------------------------------------------ library (photos + source files)
_LIBRARY_FILE = _DATA_DIR / "library.json"
_library: List[Dict[str, Any]] = []


def _save_library() -> None:
    _write(_LIBRARY_FILE, json.dumps(_library, ensure_ascii=False, indent=2))


def add_library_item(meta: dict) -> dict:
    with _lock:
        row = {"id": str(uuid.uuid4()), "host_key": normalize_host_key(meta.get("host_key") or ""),
               "organism_type": meta.get("organism_type") or "crop",
               "title": (meta.get("title") or meta.get("filename") or "Untitled")[:200],
               "condition_label": (meta.get("condition_label") or "")[:200],
               "signs": (meta.get("signs") or "")[:1000], "notes": (meta.get("notes") or "")[:2000],
               "filename": (meta.get("filename") or "")[:200],
               "content_type": meta.get("content_type") or "application/octet-stream",
               "stored_name": meta.get("stored_name") or "", "size_bytes": meta.get("size_bytes") or 0,
               "created_at": _now(), "use_for_ml": bool(meta.get("use_for_ml", True)),
               "extracted_text": (meta.get("extracted_text") or "")[:50000], "procedure_ids": []}
        _library.append(row)
        _save_library()
        return row


def link_library_procedure(library_id: str, procedure_id: str) -> None:
    with _lock:
        for it in _library:
            if it.get("id") == library_id:
                it.setdefault("procedure_ids", [])
                if procedure_id not in it["procedure_ids"]:
                    it["procedure_ids"].append(procedure_id)
                it["procedure_id"] = procedure_id
                _save_library()
                return


def _published_ids() -> set:
    return {p["id"] for p in _procedures if p.get("status") == "published"}


def list_library(host_key: Optional[str] = None, public: bool = False) -> List[dict]:
    """public=True: only items tied to a published procedure, without raw extracted text."""
    with _lock:
        rows = list(_library)
        pub = _published_ids()
    if host_key:
        hk = normalize_host_key(host_key)
        rows = [x for x in rows if x.get("host_key") == hk]
    if public:
        rows = [{k: v for k, v in x.items() if k != "extracted_text"} for x in rows
                if set(x.get("procedure_ids") or []) & pub]
    return list(reversed(rows))


def library_item_by_file(stored_name: str) -> Optional[dict]:
    with _lock:
        return next((x for x in _library if x.get("stored_name") == stored_name), None)


def library_file_is_public(stored_name: str) -> bool:
    it = library_item_by_file(stored_name)
    if not it:
        return False
    ct = (it.get("content_type") or "").lower()
    is_img = ct.startswith("image/")
    return is_img and bool(set(it.get("procedure_ids") or []) & _published_ids())


def _norm_label(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def resolve_condition_bundle(host_key: str, condition_hint: str = "", language: str = "en") -> dict:
    """Join labelled photos to PUBLISHED procedures (explicit link first, then label match)."""
    hk = normalize_host_key(host_key)
    with _lock:
        pubs = [p for p in _procedures if p.get("status") == "published" and p.get("host_key") == hk]
        libs = [x for x in _library if x.get("host_key") == hk and (x.get("content_type") or "").startswith("image/")]
    bundles = []
    for it in libs:
        match = next((p for p in pubs if p["id"] in (it.get("procedure_ids") or [])), None)
        if not match:
            lab = _norm_label(it.get("condition_label") or "")
            for p in pubs:
                for t in (p.get("title") or {}).values():
                    n = _norm_label(t)
                    if lab and n and (lab == n or lab in n or n in lab):
                        match = p
                        break
                if match:
                    break
        if not match:
            continue
        title = (match.get("title") or {}).get(language) or next(iter((match.get("title") or {}).values()), "")
        bundles.append({"condition_name": title, "matched_procedure_id": match["id"],
                        "image_url": f"/v1/library/file/{it['stored_name']}" if it.get("stored_name") else None})
    return {"host_key": hk, "bundles": bundles, "images": [b for b in bundles if b["image_url"]]}


# ------------------------------------------------------------------------------------------------ farms, outbreaks, alerts
_farms: Dict[str, Dict[str, Any]] = {}
_outbreaks: List[Dict[str, Any]] = []
_alerts: List[Dict[str, Any]] = []
_ALERTS_FILE = _DATA_DIR / "alerts.json"
_OUTBREAKS_FILE = _DATA_DIR / "outbreaks.json"


def get_farm(device_id: str) -> dict:
    with _lock:
        return _farms.get(device_id) or {"device_id": device_id, "hosts": [], "notes": "", "updated_at": None}


def save_farm(device_id: str, hosts: List[dict], notes: str = "") -> dict:
    with _lock:
        row = {"device_id": device_id, "hosts": hosts[:40], "notes": notes[:1000], "updated_at": _now()}
        _farms[device_id] = row
        return row


def add_outbreak(body: dict) -> dict:
    global _cursor
    with _lock:
        row = {"id": str(uuid.uuid4()), "created_at": _now(), "status": "under_review",
               "organism_type": body.get("organism_type") or "crop", "host_key": normalize_host_key(body.get("host_key") or ""),
               "district": (body.get("district") or "Lilongwe")[:60], "ward": (body.get("ward") or None),
               "country_code": (body.get("country_code") or "MW").upper()[:2],
               "number_affected": body.get("number_affected"), "severity": body.get("severity") or "moderate",
               "notes": (body.get("notes") or "")[:1000]}
        _outbreaks.append(row)
        _cursor += 1
        _write(_OUTBREAKS_FILE, json.dumps(_outbreaks, ensure_ascii=False))
        return row


def confirm_outbreak(oid: str, confirmed: bool, reviewer: str = "") -> Optional[dict]:
    global _cursor
    with _lock:
        for row in _outbreaks:
            if row["id"] == oid:
                row["status"] = "confirmed" if confirmed else "rejected"
                row["reviewed_by"] = reviewer[:120]
                _cursor += 1
                if confirmed:
                    _alerts.append({"id": str(uuid.uuid4()), "title": f"{row.get('host_key')} - {row.get('ward') or row.get('district')}",
                                    "body": "Confirmed area report. Follow extension guidance.", "district": row.get("district"),
                                    "ward": row.get("ward"), "country_code": row.get("country_code"), "status": "published",
                                    "level": "confirmed", "created_at": _now(),
                                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()})
                _write(_OUTBREAKS_FILE, json.dumps(_outbreaks, ensure_ascii=False))
                _write(_ALERTS_FILE, json.dumps(_alerts, ensure_ascii=False))
                return row
        return None


def publish_alert(title: str, body: str, district: str, host_key: str = "", level: str = "watch", days: int = 7) -> dict:
    """Expert-published alert. level 'watch' = suspected, 'confirmed' = red alert."""
    global _cursor
    with _lock:
        row = {"id": str(uuid.uuid4()), "title": title[:140], "body": body[:600], "district": district[:60],
               "host_key": normalize_host_key(host_key), "status": "published", "level": level,
               "created_at": _now(), "expires_at": (datetime.now(timezone.utc) + timedelta(days=max(1, min(days, 60)))).isoformat()}
        _alerts.append(row)
        _cursor += 1
        _write(_ALERTS_FILE, json.dumps(_alerts, ensure_ascii=False))
        return row


def list_outbreaks(district: str = "Lilongwe") -> List[dict]:
    with _lock:
        return [o for o in reversed(_outbreaks) if o.get("district") == district]


def list_alerts(district: str = "Lilongwe") -> List[dict]:
    now = _now()
    with _lock:
        return [a for a in reversed(_alerts) if a.get("status") == "published" and (a.get("expires_at") or "9") > now
                and (district in ("", "all") or a.get("district") in (district, "all"))]


def district_summary(country: str = "MW", district: str = "Lilongwe") -> dict:
    with _lock:
        rows = [o for o in _outbreaks if o.get("district") == district and o.get("status") in ("confirmed", "under_review")]
        by_ward: Dict[str, int] = {}
        for o in rows:
            w = o.get("ward") or "unspecified"
            by_ward[w] = by_ward.get(w, 0) + 1
        hot = [{"ward": w, "report_count": c, "level": "high" if c >= 3 else "moderate" if c >= 2 else "low"}
               for w, c in sorted(by_ward.items(), key=lambda x: -x[1])]
        return {"country": country.upper(), "district": district, "total_reports": len(rows),
                "confirmed": sum(1 for o in rows if o.get("status") == "confirmed"),
                "under_review": sum(1 for o in rows if o.get("status") == "under_review"),
                "outbreak_hotspots": hot, "alerts_active": list_alerts(district),
                "published_procedures": len(list_procedures()), "note": "Area-level only. No farm names.",
                "sync_cursor": _cursor}


def sync_delta(cursor: int, country: str = "MW", district: str = "Lilongwe") -> dict:
    return {"cursor": _cursor, "since": cursor, "has_changes": _cursor > cursor,
            "experts": list_experts(country, district), "alerts": list_alerts(district),
            "published_procedures": list_procedures(), "district_summary": district_summary(country, district)}


# ------------------------------------------------------------------------------------------------ push tokens, contributions
_PUSH_FILE = _DATA_DIR / "push_tokens.json"
_push: List[Dict[str, Any]] = []
_CONTRIB_FILE = _DATA_DIR / "contributions.json"
_contribs: List[Dict[str, Any]] = []


def register_push_token(body: dict) -> dict:
    global _push
    with _lock:
        token = (body.get("token") or "").strip()[:512]
        if not token:
            raise ValueError("token required")
        _push = [t for t in _push if t.get("token") != token]
        _push.append({"token": token, "device_id": (body.get("device_id") or "")[:64],
                      "platform": body.get("platform") if body.get("platform") in ("android", "ios") else "android", "at": _now()})
        _push = _push[-5000:]
        _write(_PUSH_FILE, json.dumps(_push))
        return {"ok": True, "registered": len(_push)}


def list_push_tokens() -> List[dict]:
    with _lock:
        return list(_push)


def add_contribution(body: dict) -> dict:
    """Farmer observation kept for expert review only. Never shown to other farmers, never auto-published."""
    with _lock:
        row = {"id": str(uuid.uuid4()), "at": _now(), "host_key": normalize_host_key(body.get("host_key") or ""),
               "language": (body.get("language") or "en")[:2], "farmer_description": (body.get("farmer_description") or "")[:1500],
               "status": "pending_expert_review"}
        _contribs.append(row)
        del _contribs[:-3000]
        _write(_CONTRIB_FILE, json.dumps(_contribs, ensure_ascii=False))
        return row


def list_contributions() -> List[dict]:
    with _lock:
        return list(_contribs[-500:])


def _load_all() -> None:
    global _experts, _library, _chats, _alerts, _outbreaks, _push, _contribs
    _load_procedures()
    _experts = _read_json(_EXPERTS_FILE, []) or []
    _library = _read_json(_LIBRARY_FILE, []) or []
    _chats = _read_json(_CHAT_FILE, {}, encrypted=True) or {}
    _alerts = _read_json(_ALERTS_FILE, []) or []
    _outbreaks = _read_json(_OUTBREAKS_FILE, []) or []
    _push = _read_json(_PUSH_FILE, []) or []
    _contribs = _read_json(_CONTRIB_FILE, []) or []
    for it in _library:
        it["host_key"] = normalize_host_key(it.get("host_key") or "")
    for it in _library:                       # migrate old single link -> list
        if it.get("procedure_id") and not it.get("procedure_ids"):
            it["procedure_ids"] = [it["procedure_id"]]


_load_all()
