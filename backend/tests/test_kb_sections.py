from app import kb_engine as K
from app import structure as S

CRIT = {"en": ["Isolate the animal."]}
crit = lambda l: CRIT.get(l, CRIT["en"])
DOC = """Late blight
Type: disease
Signs: dark water-soaked spots; white mould under leaves
Symptoms: leaves wither quickly
Treatment:
- Remove and burn infected plants
Medication: copper fungicide
Dose: 2 g per litre of water
Withdrawal: 7 days before harvest
Prevention:
- Rotate crops
When to refer: if more than half of the field is affected

Bacterial wilt
Signs: sudden wilting of whole plant
Prevention: use clean seed
"""

def published(verified=False, src=""):
    out = []
    for i, d in enumerate(S.drafts_from_text(DOC, "tomato", "en", "vet_guide.pdf")):
        d.update(id=f"p{i}", status="published", approved_by="Dr Banda", updated_at="2026-02-01T00:00:00Z")
        if verified and d["title"]["en"] == "Late blight":
            d.update(dose_verified=True, dose_source=src)
        out.append(d)
    return out

def ask(procs, msg, host="tomato", lang="en", prior=None, aliases=None):
    idx = K.Index(procs, 1, aliases)
    return K.answer(idx, msg, lang, host, critical_steps=crit, prior=prior)

def test_all_sections_shown_but_dose_hidden_when_unverified():
    r = ask(published(), "water soaked spots on tomato leaves wither")
    assert r["outcome"] == "answer"
    t = r["reply"]
    for needle in ("Type: disease", "dark water-soaked spots", "leaves wither", "Remove and burn", "copper fungicide",
                   "Rotate crops", "more than half"):
        assert needle in t, needle
    assert "2 g per litre" not in t and "7 days" not in t
    assert K.UI["en"]["dose_ask"] in t and K.UI["en"]["chem_note"] in t

def test_dose_shown_when_vet_verified_with_source():
    r = ask(published(True, "Dept of Agriculture Pesticide Register 2025"), "water soaked spots on tomato leaves")
    assert "2 g per litre" in r["reply"] and "7 days" in r["reply"]
    assert "Pesticide Register 2025" in r["reply"]

def test_dose_not_shown_if_verified_flag_without_source():
    r = ask(published(True, ""), "water soaked spots on tomato leaves")
    assert "2 g per litre" not in r["reply"]

def test_alias_from_expert_approved_local_word():
    procs = published()
    plain = ask(procs, "mafunde akuda pamasamba", lang="ny")
    assert plain["outcome"] != "answer"
    r = ask(procs, "mafunde akuda pamasamba", lang="ny", aliases={"p0": ["mafunde akuda"]})
    assert r["outcome"] == "answer" and r["procedure_ids"] == ["p0"]

def test_prior_breaks_ties_but_cannot_rescue_weak_match():
    procs = published()
    r = ask(procs, "wilting plant", prior={"p1": 1.0})
    assert r["outcome"] in ("answer", "clarify")
    weak = ask(procs, "my goat limps", host="tomato", prior={"p0": 1.0})
    assert weak["outcome"] == "not_sure"

def test_memory_note_needs_k_farmers():
    r = ask(published(), "water soaked spots on tomato leaves")
    assert K.with_memory_note(dict(r), "en", 2, 30)["memory"] is None
    r2 = K.with_memory_note(dict(r), "en", 5, 30, 7)
    assert r2["memory"]["farmers"] == 5 and "5 other farmers" in r2["reply"]

def test_pack_views_and_dose_gate():
    pack = K.build_pack(published(), CRIT, 1, aliases={"p0": ["x"]}, nearby={"p0": 4, "p1": 1})
    d = [p for p in pack["procedures"] if p["id"] == "p0"][0]
    assert d["views"]["en"]["dose"] == [] and d["aliases"] == ["x"]
    assert pack["nearby"] == {"p0": 4}

def test_numbers_at_line_start_are_never_stripped():
    d = S.drafts_from_text("Mange\nDose:\n- 2 ml per litre\n3. 5 g per animal\nTreatment:\n1. Isolate animal\n", "goats", "en", "f.txt")
    dose = d[0]["sections"]["en"]["dose"]
    assert dose == ["2 ml per litre", "5 g per animal"]
    assert d[0]["sections"]["en"]["treatment"] == ["Isolate animal"]
    assert K._clean_line("- 2 g per litre of water") == "2 g per litre of water"
    assert K._clean_line("1. Remove leaves") == "Remove leaves"
