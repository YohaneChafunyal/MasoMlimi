import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app import host_detector as H, main

def jpeg():
    b = io.BytesIO(); Image.new("RGB", (64, 64), (30, 120, 40)).save(b, "JPEG"); return b.getvalue()

def fake(scores):
    full = {h: 0.0 for h in H.ALL}; full.update(scores)
    H.set_backend(lambda _img: full, "fake")

@pytest.fixture(autouse=True)
def reset():
    yield
    H.set_backend(None)

def test_no_backend_means_farmer_chooses_from_list_guided_hosts_first():
    H.set_backend(None)
    r = H.identify(b"x", "livestock", {"goats": 2})
    assert r["candidates"] == [] and not r["confident"] and r["suggested"] is None and r["validated"] is False
    assert r["choices"][0] == {"host_key": "goats", "has_guidance": True}

def test_confident_only_when_clear_winner():
    fake({"maize": 0.86, "cassava": 0.06, "tomato": 0.04, "beans": 0.04})
    r = H.identify(b"x", "crop")
    assert r["confident"] and r["suggested"] == "maize" and r["candidates"][0]["band"] == "high"
    fake({"maize": 0.45, "cassava": 0.40, "tomato": 0.15})
    r = H.identify(b"x", "crop")
    assert not r["confident"] and r["suggested"] is None and len(r["candidates"]) >= 2   # close call: ask the farmer

def test_photo_of_other_category_asks_to_switch_not_to_guess():
    fake({"goats": 0.80, "cattle": 0.10, "maize": 0.06, "tomato": 0.04})
    r = H.identify(b"x", "crop")
    assert r["organism_mismatch"] == "livestock" and not r["confident"] and r["suggested"] is None
    fake({"maize": 0.9, "tomato": 0.1})
    assert H.identify(b"x", "livestock")["organism_mismatch"] == "crop"

def test_candidates_only_from_chosen_category_and_flag_guidance():
    fake({"chicken": 0.7, "goats": 0.2, "cattle": 0.1})
    r = H.identify(b"x", "livestock", {"chicken": 1})
    assert {c["host_key"] for c in r["candidates"]} <= set(H.LIVESTOCK) and r["candidates"][0]["has_guidance"] is True

def test_backend_failure_degrades_to_list():
    def boom(_): raise RuntimeError("model crashed")
    H.set_backend(boom, "broken")
    r = H.identify(b"x", "crop")
    assert r["candidates"] == [] and r["choices"]

def test_endpoint_open_to_farmers_validated_and_limited():
    c = TestClient(main.app)
    fake({"tomato": 0.9, "maize": 0.05, "cassava": 0.05})
    ok = c.post("/v1/scan/identify", data={"organism_hint": "crop"}, files={"image": ("p.jpg", jpeg(), "image/jpeg")})
    assert ok.status_code == 200 and ok.json()["suggested"] == "tomato" and ok.json()["validated"] is False
    assert c.post("/v1/scan/identify", data={"organism_hint": "crop"}, files={"image": ("p.jpg", b"notanimage" * 10, "image/jpeg")}).status_code == 415
    assert c.post("/v1/scan/identify", data={"organism_hint": "fish"}, files={"image": ("p.jpg", jpeg(), "image/jpeg")}).status_code == 422

def test_feedback_tracks_agreement_and_confusions():
    c = TestClient(main.app)
    c.post("/v1/scan/identify/feedback", json={"detected": "maize", "chosen": "maize", "organism": "crop"})
    c.post("/v1/scan/identify/feedback", json={"detected": "maize", "chosen": "sorghum", "organism": "crop"})
    assert c.post("/v1/scan/identify/feedback", json={"detected": "maize", "chosen": "dragon"}).status_code == 422
    st = H.stats()
    assert st["total"] >= 2 and st["agreed"] >= 1 and st["confusions"].get("maize->sorghum", 0) >= 1
