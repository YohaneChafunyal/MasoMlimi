"""One code path for farmer chat AND photo scan: published content -> engine -> memory -> response.

`store` is the app.store module (or a stand-in in tests). `translate` is an optional callable
(context, lang) -> str used ONLY to translate approved text; its output is number-verified.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Callable, Dict, List, Optional

from app import kb_engine, memory

LIVESTOCK_DANGER_KEYS = {"sudden_many_dead", "bloody_discharge", "cannot_stand", "high_fever_group"}


def device_hash(device_id: str) -> str:
    salt = (os.environ.get("MASOMLIMI_PRIVACY_SALT") or "masomlimi-pilot").encode()
    return hashlib.sha256(salt + (device_id or "").encode()).hexdigest()[:16] if device_id else ""


def get_index(store) -> kb_engine.Index:
    return kb_engine.get_index(store.list_procedures(include_draft=False),
                               (store.content_version(), memory.alias_version()), memory.approved_aliases())


def _images(store, host: str, ans: dict, lang: str) -> None:
    if ans["outcome"] not in ("answer", "catalog") or not host:
        return
    try:
        name = ans["passages"][0]["name"] if ans.get("passages") else ""
        bun = store.resolve_condition_bundle(host, name, lang)
        keep = set(ans.get("procedure_ids") or [])
        ans["images"] = [{"image_url": b["image_url"], "title": b["condition_name"]} for b in bun.get("bundles", [])
                         if b.get("image_url") and (not keep or b.get("matched_procedure_id") in keep)][:3]
    except Exception:
        pass


def _finish(store, idx, ans: dict, *, dev: str, host: str, district: str, lang: str, source: str,
            photo: str = "", translate: Optional[Callable[[str, str], str]] = None) -> dict:
    q = ans.get("query_tokens") or []
    proc = ans["procedure_ids"][0] if ans.get("procedure_ids") and len(ans["procedure_ids"]) == 1 else ""
    # similar cases from OTHER farmers (k-anonymous)
    if ans["outcome"] == "answer" and proc:
        sim = memory.similar(host, q, proc, district, days=30, exclude_dev=dev)
        kb_engine.with_memory_note(ans, lang, sim["farmers"], 30, sim["cases"])
    # case memory (not for empty prompts)
    if ans["outcome"] not in ("prompt", "smalltalk") and q:
        c = memory.record_case(dev, host, district, q, proc, ans["outcome"], ans["confidence"]["band"],
                               ans["confidence"]["coverage"], source=source, photo=photo, lang=lang)
        ans["case_id"] = c["id"]
        if ans["outcome"] == "answer":
            L = kb_engine.UI[lang]
            ans["feedback"] = {"question": L["feedback_q"], "yes": L["fb_yes"], "no": L["fb_no"]}
    _images(store, host, ans, lang)
    if ans["outcome"] == "answer" and ans.get("needs_translation") and translate:
        t = translate(ans.get("llm_context", ""), lang)
        if t and kb_engine.verify_llm_output(t, ans["llm_context"]):
            ans = kb_engine.finalize_translation(ans, t, lang)
    ans.pop("llm_context", None)
    ans.pop("text_parts", None)
    return ans


def chat(store, body: dict, translate: Optional[Callable[[str, str], str]] = None) -> dict:
    lang = body.get("language") if body.get("language") in kb_engine.LANGS else "en"
    host_in = body.get("host_key") or body.get("host") or ""
    host = store.normalize_host_key(host_in) if host_in else ""
    message, desc = str(body.get("message") or body.get("text") or ""), str(body.get("description") or "")
    district = str(body.get("district") or "")
    dev = device_hash(str(body.get("device_id") or ""))
    idx = get_index(store)
    q = kb_engine.query_tokens(message, desc, host)
    ans = kb_engine.answer(idx, message, lang, host, desc, critical_steps=store.critical_steps,
                           normalize_host=store.normalize_host_key, prior=memory.prior(host, q, district))
    ans["query_tokens"] = ans.get("query_tokens") or q
    return _finish(store, idx, ans, dev=dev, host=host, district=district, lang=lang, source="chat",
                   translate=translate if body.get("use_llm", True) else None)


def scan(store, *, host_key: str, organism: str, lang: str, device_id: str, district: str,
         symptom_keys: List[str], notes: str, danger_flag: bool, image: bytes,
         translate: Optional[Callable[[str, str], str]] = None) -> dict:
    lang = lang if lang in kb_engine.LANGS else "en"
    host = store.normalize_host_key(host_key) if host_key else ""
    dev = device_hash(device_id)
    idx = get_index(store)
    words = " ".join(k.replace("_", " ") for k in symptom_keys)
    message = f"{words} {notes}".strip()
    q = kb_engine.query_tokens(message, "", host)
    livestock = organism == "livestock" or host in kb_engine.LIVESTOCK
    if livestock and (danger_flag or set(symptom_keys) & LIVESTOCK_DANGER_KEYS):
        ans = kb_engine.emergency(lang, store.critical_steps, reason="danger_signs_selected")
        ans["query_tokens"] = q or ["danger"]
    else:
        ans = kb_engine.answer(idx, message, lang, host, "", critical_steps=store.critical_steps,
                               normalize_host=store.normalize_host_key, prior=memory.prior(host, q, district))
        ans["query_tokens"] = ans.get("query_tokens") or q
    ph = memory.photo_hash(image) if image else ""
    pm = memory.photo_matches(host, ph, exclude_dev=dev) if ph else {"farmers": 0, "helped": []}
    ans = _finish(store, idx, ans, dev=dev, host=host, district=district, lang=lang, source="scan", photo=ph,
                  translate=translate)
    # photo memory is only a hint, only above the privacy threshold, never a diagnosis
    ans["photo_hint"] = {"similar_photos_from_farmers": pm["farmers"] if pm["farmers"] >= memory.K_MIN_FARMERS else 0,
                         "is_diagnosis": False}
    ans["ml"] = {"certified": False, "model_loaded": False,
                 "note": "Photo is stored as a fingerprint only. Advice comes from the symptoms you selected and the published library. "
                         "A validated photo model is a launch gate."}
    # compatibility fields used by the existing ResultPage
    sec = ans.get("sections") or {}
    color = "red" if ans["outcome"] == "emergency" else ("amber" if (ans["outcome"] != "answer" or ans.get("has_medicine")) else "green")
    ans["result_color"] = color
    ans["confidence_band"] = ans["confidence"]["band"]
    ans["condition"] = ({"id": (ans.get("procedure_ids") or [None])[0], "common_name": ans["passages"][0]["name"],
                         "is_dangerous": False} if ans.get("passages") else None)
    steps = (sec.get("treatment") or []) + (["%s: %s" % (kb_engine.UI[lang]["dose_label"], d) for d in sec.get("dose") or []])
    ans["procedure_steps"] = [{"type": "published", "text": s} for s in steps]
    ans["prevention_steps"] = [{"type": "prevention", "text": s} for s in (sec.get("prevention") or [])]
    ans["products"] = [{"name": m} for m in sec.get("medication") or []]
    ans["messages"] = {"primary": ans["reply"].split("\n", 1)[0], "ask_expert_note": kb_engine.UI[lang]["ask_expert"]}
    ans["from_published_library"] = ans["outcome"] == "answer"
    return ans


def give_feedback(case_id: str, helped: str, store) -> bool:
    idx = get_index(store)
    return memory.feedback(case_id, helped, idx.doc_tokens) is not None
