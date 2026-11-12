"""Case memory: what farmers asked/scanned, what the engine matched, and whether it helped.

What "learning" means here (and what it does NOT mean):
  * Every chat question and scan is stored as an anonymous case: hashed device id, district, host, normalised
    word tokens (not raw text), matched condition id, confidence, optional photo fingerprint.
  * SIMILAR CASES: "N other farmers near you asked about a similar problem" - shown only when >= K devices.
  * PRIOR: cases the farmer marked "this helped" nudge ranking between candidates that ALREADY pass the
    confidence threshold. Unconfirmed cases never influence ranking (no feedback loop on its own mistakes).
  * LOCAL WORDS: words farmers use for a condition (after "helped" feedback, from >= K devices) become alias
    SUGGESTIONS. They affect matching only after an expert approves them in the portal.
  * The memory NEVER edits advice text, treatments, doses or the emergency rules. Only experts publish.
  * Photo fingerprints are weak "seen a similar photo" hints, never a diagnosis.
"""
from __future__ import annotations

import io
import json
import os
import threading
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

K_MIN_FARMERS = 3
RETENTION_DAYS = int(os.environ.get("MASOMLIMI_RETENTION_DAYS", "180"))
_DIR = Path(os.environ.get("MASOMLIMI_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data")))
_CASES_FILE = _DIR / "case_memory.json"
_ALIAS_FILE = _DIR / "aliases.json"
_SUGG_FILE = _DIR / "alias_suggestions.json"
_lock = threading.RLock()
_cases: List[Dict[str, Any]] = []
_aliases: Dict[str, List[str]] = {}          # approved: procedure_id -> tokens
_sugg: Dict[str, Dict[str, Any]] = {}        # "pid|token" -> {pid, token, devices:[...], status}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load() -> None:
    global _cases, _aliases, _sugg
    for path, name in ((_CASES_FILE, "_cases"), (_ALIAS_FILE, "_aliases"), (_SUGG_FILE, "_sugg")):
        try:
            if path.is_file():
                globals()[name] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass


def _save(which: str = "all") -> None:
    try:
        _DIR.mkdir(parents=True, exist_ok=True)
        if which in ("all", "cases"):
            _CASES_FILE.write_text(json.dumps(_cases[-20000:], ensure_ascii=False), encoding="utf-8")
        if which in ("all", "aliases"):
            _ALIAS_FILE.write_text(json.dumps(_aliases, ensure_ascii=False), encoding="utf-8")
            _SUGG_FILE.write_text(json.dumps(_sugg, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def reset_for_tests(data_dir: Path) -> None:
    global _DIR, _CASES_FILE, _ALIAS_FILE, _SUGG_FILE, _cases, _aliases, _sugg
    _DIR = Path(data_dir)
    _CASES_FILE, _ALIAS_FILE, _SUGG_FILE = _DIR / "case_memory.json", _DIR / "aliases.json", _DIR / "alias_suggestions.json"
    _cases, _aliases, _sugg = [], {}, {}


def _ts(c: dict) -> datetime:
    try:
        return datetime.fromisoformat(c["at"])
    except Exception:
        return _now() - timedelta(days=9999)


def purge() -> int:
    """Retention limit: drop cases older than RETENTION_DAYS."""
    global _cases
    with _lock:
        cutoff = _now() - timedelta(days=RETENTION_DAYS)
        before = len(_cases)
        _cases = [c for c in _cases if _ts(c) >= cutoff]
        if len(_cases) != before:
            _save("cases")
        return before - len(_cases)


def delete_device(device_hash: str) -> int:
    """'Delete my data' request."""
    global _cases
    with _lock:
        before = len(_cases)
        _cases = [c for c in _cases if c.get("dev") != device_hash]
        _save("cases")
        return before - len(_cases)


def photo_hash(data: bytes) -> str:
    """64-bit difference hash (dHash). Weak similarity hint only. Empty if Pillow is unavailable."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("L").resize((9, 8))
        px = list(im.getdata())
        bits = 0
        for r in range(8):
            for c in range(8):
                bits = (bits << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
        return f"{bits:016x}"
    except Exception:
        return ""


def _hamming(a: str, b: str) -> int:
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except Exception:
        return 64


def _sim(a: List[str], b: List[str]) -> float:
    A, B = set(a), set(b)
    return (len(A & B) / len(A | B)) if A and B else 0.0


def record_case(dev: str, host: str, district: str, tokens: List[str], proc_id: str, outcome: str, band: str,
                coverage: float, source: str = "chat", photo: str = "", lang: str = "en") -> dict:
    with _lock:
        c = {"id": uuid.uuid4().hex, "at": _now().isoformat(), "dev": dev, "host": host, "district": district or "",
             "tokens": list(dict.fromkeys(tokens))[:24], "proc": proc_id or "", "outcome": outcome, "band": band,
             "cov": coverage, "src": source, "photo": photo, "lang": lang, "fb": ""}
        _cases.append(c)
        if len(_cases) % 50 == 0:
            purge()
        _save("cases")
        return c


def feedback(case_id: str, helped: str, known_tokens_for: Optional[Any] = None) -> Optional[dict]:
    """helped: 'yes' | 'no'. On 'yes', words the farmer used that the condition's text lacks become alias suggestions."""
    if helped not in ("yes", "no"):
        return None
    with _lock:
        for c in _cases:
            if c["id"] == case_id:
                c["fb"] = helped
                if helped == "yes" and c.get("proc") and c.get("outcome") == "answer" and known_tokens_for:
                    known = known_tokens_for(c["proc"])
                    for tok in c["tokens"]:
                        if tok in known or len(tok) < 4:
                            continue
                        key = f"{c['proc']}|{tok}"
                        s = _sugg.setdefault(key, {"pid": c["proc"], "token": tok, "devices": [], "status": "pending"})
                        if c["dev"] not in s["devices"]:
                            s["devices"].append(c["dev"])
                _save("all")
                return c
    return None


def similar(host: str, tokens: List[str], proc_id: str = "", district: str = "", days: int = 30,
            min_sim: float = 0.34, exclude_dev: str = "") -> Dict[str, Any]:
    cutoff = _now() - timedelta(days=days)
    devs, n, last = set(), 0, None
    by_proc: Counter = Counter()
    helped: Counter = Counter()
    with _lock:
        rows = list(_cases)
    for c in rows:
        if c.get("host") != host or _ts(c) < cutoff or c.get("dev") == exclude_dev:
            continue
        if district and c.get("district") and c["district"] != district:
            continue
        if _sim(tokens, c.get("tokens", [])) < min_sim:
            continue
        if proc_id and c.get("proc") != proc_id:
            continue
        n += 1
        devs.add(c["dev"])
        if c.get("proc"):
            by_proc[c["proc"]] += 1
            if c.get("fb") == "yes":
                helped[c["proc"]] += 1
        t = _ts(c)
        last = t if (last is None or t > last) else last
    return {"cases": n, "farmers": len(devs), "last_days": (_now() - last).days if last else None,
            "top": by_proc.most_common(3), "helped": helped.most_common(3)}


def prior(host: str, tokens: List[str], district: str = "") -> Dict[str, float]:
    """Weights in [0,1] from cases that were answered AND marked helpful."""
    acc: Dict[str, float] = defaultdict(float)
    with _lock:
        rows = list(_cases)
    for c in rows:
        if c.get("host") != host or c.get("fb") != "yes" or c.get("outcome") != "answer" or not c.get("proc"):
            continue
        s = _sim(tokens, c.get("tokens", []))
        if s >= 0.34:
            acc[c["proc"]] += s
    return {k: min(1.0, v / 3.0) for k, v in acc.items()}


def photo_matches(host: str, ph: str, exclude_dev: str = "", max_dist: int = 6) -> Dict[str, Any]:
    """Weak hint: same-host photos that look near-identical and were later confirmed helpful."""
    if not ph:
        return {"similar_photos": 0, "farmers": 0, "helped": []}
    devs, helped = set(), Counter()
    with _lock:
        rows = list(_cases)
    for c in rows:
        if c.get("host") != host or not c.get("photo") or c.get("dev") == exclude_dev:
            continue
        if _hamming(ph, c["photo"]) <= max_dist:
            devs.add(c["dev"])
            if c.get("fb") == "yes" and c.get("proc"):
                helped[c["proc"]] += 1
    return {"similar_photos": len(devs), "farmers": len(devs), "helped": helped.most_common(3)}


def nearby_counts(district: str = "", days: int = 30) -> Dict[str, int]:
    """procedure_id -> distinct farmers (k-anonymity enforced by consumers)."""
    cutoff = _now() - timedelta(days=days)
    devs: Dict[str, set] = defaultdict(set)
    with _lock:
        rows = list(_cases)
    for c in rows:
        if c.get("outcome") != "answer" or not c.get("proc") or _ts(c) < cutoff:
            continue
        if district and c.get("district") and c["district"] != district:
            continue
        devs[c["proc"]].add(c["dev"])
    return {k: len(v) for k, v in devs.items()}


def trends(district: str = "", days: int = 14, min_farmers: int = K_MIN_FARMERS) -> List[dict]:
    """For the expert portal: candidate WATCH signals. Alerts are still published by experts only."""
    counts = nearby_counts(district, days)
    return [{"procedure_id": k, "farmers": v, "days": days, "district": district or "all"}
            for k, v in sorted(counts.items(), key=lambda x: -x[1]) if v >= min_farmers]


# ---- expert-approved local words -----------------------------------------------------------
def alias_version() -> int:
    return sum(len(v) for v in _aliases.values())


def approved_aliases() -> Dict[str, List[str]]:
    with _lock:
        return {k: list(v) for k, v in _aliases.items()}


def suggestions(min_farmers: int = K_MIN_FARMERS) -> List[dict]:
    with _lock:
        return [{"pid": s["pid"], "token": s["token"], "farmers": len(s["devices"]), "status": s["status"]}
                for s in _sugg.values() if s["status"] == "pending" and len(s["devices"]) >= min_farmers]


def approve_alias(pid: str, token: str, approved: bool = True) -> bool:
    key = f"{pid}|{token}"
    with _lock:
        s = _sugg.get(key)
        if not s:
            return False
        s["status"] = "approved" if approved else "rejected"
        if approved:
            _aliases.setdefault(pid, [])
            if token not in _aliases[pid]:
                _aliases[pid].append(token)
        _save("aliases")
        return True


def add_alias(pid: str, phrase: str) -> None:
    """Expert types a local name directly in the portal."""
    with _lock:
        _aliases.setdefault(pid, [])
        if phrase and phrase not in _aliases[pid]:
            _aliases[pid].append(phrase)
        _save("aliases")


def dashboard(district: str = "", hours: int = 336) -> Dict[str, Any]:
    """Portal numbers from anonymous cases (no device ids leave this function)."""
    cutoff = _now() - timedelta(hours=hours)
    with _lock:
        rows = [c for c in _cases if _ts(c) >= cutoff and (not district or district == "all" or c.get("district") in ("", district))]
    by_host: Counter = Counter(c["host"] for c in rows if c.get("host"))
    conds: Dict[str, Counter] = defaultdict(Counter)
    for c in rows:
        if c.get("proc"):
            conds[c["host"]][c["proc"]] += 1
    outcomes = Counter(c.get("outcome", "") for c in rows)
    helped = Counter(c.get("fb", "") for c in rows if c.get("fb"))
    recent = sorted(rows, key=lambda c: c.get("at", ""), reverse=True)[:30]
    return {"window_hours": hours, "total_scans": len(rows), "outcomes": dict(outcomes), "feedback": dict(helped),
            "top_hosts": [{"host_key": h, "count": n, "conditions": dict(conds.get(h, {}))} for h, n in by_host.most_common(12)],
            "recent_scans": [{"at": c["at"], "host_key": c["host"], "outcome": c["outcome"], "band": c["band"],
                              "source": c["src"], "district": c["district"], "procedure_id": c["proc"]} for c in recent]}


_load()
