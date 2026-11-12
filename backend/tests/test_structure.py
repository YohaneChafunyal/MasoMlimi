from app import structure as S

DOC = """African Crop Guide
Late blight
Type: disease
Signs: dark water-soaked spots; white mould under leaves
Symptoms: leaves wither quickly
Treatment:
- Remove and burn infected plants
- Do not water in the evening
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

def test_split_two_conditions():
    segs = S.split_conditions(DOC)
    titles = [s["title"] for s in segs]
    assert "Late blight" in titles and "Bacterial wilt" in titles

def test_structured_fields():
    d = S.drafts_from_text(DOC, "tomato", "en", "guide.pdf")
    lb = [x for x in d if x["title"]["en"] == "Late blight"][0]
    sec = lb["sections"]["en"]
    assert sec["condition_type"] == "disease"
    assert "dark water-soaked spots" in sec["signs"]
    assert sec["symptoms"] and sec["treatment"][0].startswith("Remove")
    assert sec["medication"] == ["copper fungicide"]
    assert any("2 g per litre" in x for x in sec["dose"]) and any("7 days" in x for x in sec["dose"])
    assert sec["refer"] and lb["dose_verified"] is False
    assert len(d) == 2

def test_unlabelled_text_never_becomes_treatment():
    d = S.drafts_from_text("Late blight\nSigns: spots\nSpray with something strong every day\n", "tomato", "en", "x.txt")
    assert d and "Spray with something strong every day" in d[0]["sections"]["en"]["signs"]
