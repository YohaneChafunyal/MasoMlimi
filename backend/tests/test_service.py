import pytest
from app import chat_service as CS, memory as M, structure as S, kb_engine as K

DOC = """Late blight
Type: disease
Signs: dark water-soaked spots; white mould under leaves
Treatment:
- Remove and burn infected plants
Medication: copper fungicide
Dose: 2 g per litre of water
Prevention:
- Rotate crops
When to refer: if more than half of the field is affected

Bacterial wilt
Signs: sudden wilting of whole plant
Treatment:
- Uproot wilted plants
"""
CRIT = {"en": ["Isolate the animal."], "ny": ["Patulani chiweto."]}

class FakeStore:
    CRITICAL = CRIT
    def __init__(self, verified=False):
        self.procs = []
        for i, d in enumerate(S.drafts_from_text(DOC, "tomato", "en", "vet.pdf")):
            d.update(id=f"p{i}", status="published", approved_by="Dr B", updated_at="2026-03-01T00:00:00Z")
            if verified and i == 0:
                d.update(dose_verified=True, dose_source="Official register 2025")
            self.procs.append(d)
        self.procs.append({"id": "dr", "status": "draft", "host_key": "tomato", "title": {"en": "Hidden"}, "steps": {"en": ["x"]}})
    def list_procedures(self, include_draft=False): return [p for p in self.procs if include_draft or p["status"] == "published"]
    def content_version(self): return len(self.procs)
    def critical_steps(self, l): return CRIT.get(l, CRIT["en"])
    def normalize_host_key(self, h): return (h or "").lower().strip()
    def resolve_condition_bundle(self, *a, **k): return {"bundles": []}

@pytest.fixture(autouse=True)
def fresh(tmp_path):
    M.reset_for_tests(tmp_path)
    K._CACHE.update(v=None, idx=None)

def chat(st, dev, msg="dark water soaked spots on tomato leaves", **kw):
    return CS.chat(st, {"message": msg, "language": "en", "host_key": "tomato", "device_id": dev,
                        "district": "Lilongwe", **kw})

def test_other_farmers_note_appears_only_from_third_device():
    st = FakeStore()
    notes = []
    for d in ("f1", "f2", "f3", "f4"):
        r = chat(st, d)
        assert r["outcome"] == "answer"
        notes.append(r["memory"])
    assert notes[0] is None and notes[1] is None and notes[2] is None
    assert notes[3]["farmers"] == 3 and "4 other farmers" in chat(st, "f5")["reply"]

def test_same_device_does_not_count_itself():
    st = FakeStore()
    for _ in range(5):
        r = chat(st, "same")
    assert r["memory"] is None

def test_feedback_teaches_prior_and_alias_after_expert_approval():
    st = FakeStore()
    for d in ("a", "b", "c"):
        r = chat(st, d, "dark spots mafunde on tomato leaves")
        assert r["outcome"] == "answer" and r["feedback"]["yes"]
        assert CS.give_feedback(r["case_id"], "yes", st)
    s = M.suggestions()
    assert any(x["token"] == "mafunde" for x in s)
    assert M.approve_alias("p0", "mafunde")
    r = chat(st, "z", "mafunde")
    assert r["outcome"] == "answer" and r["procedure_ids"] == ["p0"]

def test_scan_returns_sections_compat_fields_and_records_case():
    st = FakeStore()
    r = CS.scan(st, host_key="tomato", organism="crop", lang="en", device_id="d1", district="Lilongwe",
                symptom_keys=["spots"], notes="dark water soaked", danger_flag=False, image=b"")
    assert r["outcome"] == "answer" and r["result_color"] == "amber" and r["has_medicine"]
    assert r["procedure_steps"] and r["case_id"] and r["ml"]["certified"] is False
    assert "2 g per litre" not in r["reply"]            # unverified dose never shown
    assert M.similar("tomato", r["query_tokens"], "p0")["cases"] == 1

def test_scan_dose_visible_when_vet_verified():
    r = CS.scan(FakeStore(True), host_key="tomato", organism="crop", lang="en", device_id="d1", district="L",
                symptom_keys=["spots"], notes="dark water soaked", danger_flag=False, image=b"")
    assert "2 g per litre" in r["reply"] and any("2 g per litre" in s["text"] for s in r["procedure_steps"])

def test_scan_livestock_danger_is_fixed_red():
    r = CS.scan(FakeStore(), host_key="goats", organism="livestock", lang="ny", device_id="d", district="L",
                symptom_keys=["sudden_many_dead"], notes="", danger_flag=False, image=b"")
    assert r["outcome"] == "emergency" and r["result_color"] == "red" and "Patulani" in r["reply"]

def test_drafts_never_served_and_unknown_not_sure():
    st = FakeStore()
    assert "Hidden" not in chat(st, "a", "hidden x")["reply"]
    assert chat(st, "a", "purple elephants glowing")["outcome"] == "not_sure"

def test_old_data_with_raw_host_keys_is_migrated(tmp_path, monkeypatch):
    import json, importlib, os, sys
    from app import store as st
    old = [{"id": "a", "host_key": "Tomatoes", "status": "published", "title": {"en": "Late blight"},
            "steps": {"en": ["Remove infected leaves"]}, "prevention_steps": {"en": ["Sign: dark spots on leaves"]}, "products": []}]
    (st._DATA_DIR / "procedures.json").write_text(json.dumps({"cursor": 1, "items": old}))
    st._load_procedures()
    assert st.list_procedures()[0]["host_key"] == "tomato"
    assert st.published_by_host() == {"tomato": 1}
    st.update_procedure("a", {"host_key": "Maize "})
    assert st.get_procedure("a")["host_key"] == "maize" and st.get_procedure("a")["status"] == "draft"
