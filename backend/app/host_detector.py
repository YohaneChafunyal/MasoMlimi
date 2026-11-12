"""Suggest WHICH crop or animal is in a photo. A suggestion only: the farmer always confirms.

STATUS: demo, NOT validated on African field photos. Nothing here may be treated as a diagnosis, and no advice is
given until the farmer confirms the crop/animal. That is a launch gate (see docs/ML_LAUNCH_GATE.md).

Backends (first one available wins; pick with MASOMLIMI_DETECTOR=clip|onnx|none):
  * "clip": zero-shot CLIP via `transformers` (pip install transformers torch; weights download on first use).
            Works with no training data, so it is the quickest way to try auto-detection.
  * "onnx": your own classifier. Put  app/models/host_classifier.onnx  and  app/models/host_labels.json
            (a JSON list of host keys in output order). Input 1x3x224x224 float32, ImageNet-normalised.
  * "none": no detection: the app shows the list of crops/animals to choose from (also the offline behaviour).

Safety rules: low-confidence or close calls return confident=False (app asks the farmer to choose); a photo that
looks like the other category (animal while "Crop" was chosen) returns organism_mismatch so the app can ask to switch.
"""
from __future__ import annotations

import io
import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

CROPS = ["maize", "cassava", "tomato", "beans", "groundnuts", "rice", "tobacco"]
LIVESTOCK = ["chicken", "goats", "cattle", "pigs", "sheep", "ducks"]
ALL = CROPS + LIVESTOCK

_PROMPTS = {
    "maize": "a photo of a maize (corn) plant", "cassava": "a photo of a cassava plant", "tomato": "a photo of a tomato plant",
    "beans": "a photo of a bean plant", "groundnuts": "a photo of a groundnut (peanut) plant", "rice": "a photo of a rice plant",
    "tobacco": "a photo of a tobacco plant", "chicken": "a photo of a chicken", "goats": "a photo of a goat",
    "cattle": "a photo of a cow or cattle", "pigs": "a photo of a pig", "sheep": "a photo of a sheep", "ducks": "a photo of a duck",
}
_OTHER = "a photo of something else, not a crop or farm animal"

MIN_TOP = float(os.environ.get("MASOMLIMI_DETECT_MIN_TOP", "0.70"))
MIN_MARGIN = float(os.environ.get("MASOMLIMI_DETECT_MIN_MARGIN", "0.20"))
MISMATCH_TOP = float(os.environ.get("MASOMLIMI_DETECT_MISMATCH", "0.65"))

_MODEL_DIR = Path(__file__).resolve().parent / "models"
_lock = threading.Lock()
_backend: Optional[Callable[[bytes], Dict[str, float]]] = None
_backend_name = "none"
_loaded = False


def organism_of(host: str) -> str:
    return "livestock" if host in LIVESTOCK else "crop"


def set_backend(fn: Optional[Callable[[bytes], Dict[str, float]]], name: str = "custom") -> None:
    """For tests and custom models: fn(image_bytes) -> {host_key: probability}."""
    global _backend, _backend_name, _loaded
    _backend, _backend_name, _loaded = fn, (name if fn else "none"), True


def _load_clip():
    from transformers import pipeline  # type: ignore
    pipe = pipeline("zero-shot-image-classification", model=os.environ.get("MASOMLIMI_CLIP_MODEL", "openai/clip-vit-base-patch32"))
    labels = [_PROMPTS[h] for h in ALL] + [_OTHER]

    def run(img_bytes: bytes) -> Dict[str, float]:
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        out = pipe(img, candidate_labels=labels)
        by_label = {o["label"]: float(o["score"]) for o in out}
        return {h: by_label.get(_PROMPTS[h], 0.0) for h in ALL}
    return run


def _load_onnx():
    import numpy as np  # type: ignore
    import onnxruntime as ort  # type: ignore
    model, labels_f = _MODEL_DIR / "host_classifier.onnx", _MODEL_DIR / "host_labels.json"
    if not (model.is_file() and labels_f.is_file()):
        raise FileNotFoundError("host_classifier.onnx / host_labels.json not found")
    labels = json.loads(labels_f.read_text(encoding="utf-8"))
    sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    mean, std = np.array([0.485, 0.456, 0.406], "float32"), np.array([0.229, 0.224, 0.225], "float32")

    def run(img_bytes: bytes) -> Dict[str, float]:
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((224, 224))
        x = ((np.asarray(img, dtype="float32") / 255.0 - mean) / std).transpose(2, 0, 1)[None]
        logits = sess.run(None, {name: x})[0][0]
        e = np.exp(logits - logits.max())
        p = e / e.sum()
        return {labels[i]: float(p[i]) for i in range(min(len(labels), len(p)))}
    return run


def _ensure_loaded() -> None:
    global _backend, _backend_name, _loaded
    with _lock:
        if _loaded:
            return
        _loaded = True
        want = (os.environ.get("MASOMLIMI_DETECTOR") or "").lower()
        order = [want] if want in ("clip", "onnx") else (["onnx"] if (_MODEL_DIR / "host_classifier.onnx").is_file() else [])
        for name in order:
            try:
                _backend = _load_clip() if name == "clip" else _load_onnx()
                _backend_name = name
                return
            except Exception:
                _backend, _backend_name = None, "none"


def band(p: float) -> str:
    return "high" if p >= 0.75 else "medium" if p >= 0.45 else "low"


def identify(image: bytes, organism: str, has_guidance: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """Ranked suggestions for the chosen category. Never raises: failure means 'please choose from the list'."""
    organism = organism if organism in ("crop", "livestock") else "crop"
    pool = LIVESTOCK if organism == "livestock" else CROPS
    guid = has_guidance or {}
    base = {"organism": organism, "candidates": [], "confident": False, "suggested": None, "organism_mismatch": None,
            "model": "none", "validated": False,
            "note": "Photo recognition is a demo and not validated. The farmer must confirm what it is."}
    _ensure_loaded()
    if _backend is None:
        return {**base, "choices": _choices(pool, guid)}
    try:
        scores = _backend(image)
    except Exception:
        return {**base, "choices": _choices(pool, guid)}
    scores = {h: float(p) for h, p in scores.items() if h in ALL}
    total_all = sum(scores.values()) or 1.0
    other = LIVESTOCK if organism == "crop" else CROPS
    other_mass = sum(scores.get(h, 0.0) for h in other) / total_all
    pool_scores = {h: scores.get(h, 0.0) for h in pool}
    pool_total = sum(pool_scores.values()) or 1.0
    ranked = sorted(((h, p / pool_total * (1.0 - other_mass)) for h, p in pool_scores.items()), key=lambda x: -x[1])[:4]
    cands = [{"host_key": h, "score": round(p, 3), "band": band(p), "has_guidance": guid.get(h, 0) > 0} for h, p in ranked]
    top = ranked[0][1] if ranked else 0.0
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    confident = bool(ranked) and top >= MIN_TOP and (top - second) >= MIN_MARGIN and other_mass < 0.3
    mismatch = organism_of(other[0]) if other_mass >= MISMATCH_TOP else None
    return {**base, "candidates": cands, "confident": confident and mismatch is None,
            "suggested": cands[0]["host_key"] if (cands and confident and mismatch is None) else None,
            "organism_mismatch": mismatch, "model": _backend_name, "choices": _choices(pool, guid)}


def _choices(pool: List[str], guid: Dict[str, int]) -> List[Dict[str, Any]]:
    """The list the farmer picks from when detection is unavailable or unsure (hosts with published advice first)."""
    ordered = sorted(pool, key=lambda h: (0 if guid.get(h, 0) > 0 else 1, pool.index(h)))
    return [{"host_key": h, "has_guidance": guid.get(h, 0) > 0} for h in ordered]


# ---- monitoring: how often does the farmer agree with the suggestion? (no photos are stored) -------------------
_STATS = Path(os.environ.get("MASOMLIMI_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data"))) / "detector_stats.json"


def record_feedback(detected: str, chosen: str, organism: str) -> Dict[str, Any]:
    try:
        data = json.loads(_STATS.read_text(encoding="utf-8")) if _STATS.is_file() else {}
    except Exception:
        data = {}
    data.setdefault("total", 0)
    data.setdefault("agreed", 0)
    data.setdefault("confusions", {})
    data["total"] += 1
    if detected and detected == chosen:
        data["agreed"] += 1
    elif detected:
        k = f"{detected}->{chosen}"
        data["confusions"][k] = data["confusions"].get(k, 0) + 1
    try:
        _STATS.parent.mkdir(parents=True, exist_ok=True)
        _STATS.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass
    return data


def stats() -> Dict[str, Any]:
    try:
        d = json.loads(_STATS.read_text(encoding="utf-8")) if _STATS.is_file() else {}
    except Exception:
        d = {}
    d.setdefault("total", 0)
    d.setdefault("agreed", 0)
    d.setdefault("confusions", {})
    d["agreement_rate"] = round(d["agreed"] / d["total"], 3) if d["total"] else None
    d["backend"] = _backend_name
    return d
