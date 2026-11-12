from app import structure as S, doc_text as D, store

BOOK = """African Livestock and Crop Health Guide
Contents
Livestock: sign - possible diseases
fever - anthrax, ECF
Cattle
Anthrax
Cattle, sheep and goats
SIGNS AND
SYMPTOMS
- Sudden death
- Bleeding from nose
TREATMENT
- Do not open the carcass
PREVENTION
- Vaccinate every year
Page 12
Foot and mouth disease
Cattle, goats, pigs
SIGNS AND
SYMPTOMS
- Blisters on mouth and feet
TREATMENT
- Isolate sick animals
PREVENTION
- Restrict movement
Black quarter
Cattle
SIGNS AND
SYMPTOMS
- Swelling of hind leg
TREATMENT
- Call a vet
Heartwater
Cattle
SIGNS AND
SYMPTOMS
- Nervous signs
PREVENTION
- Tick control
"""

def test_wrapped_headings_and_subtitles():
    segs = [x["title"] for x in S.split_conditions(BOOK)]
    for t in ("Anthrax", "Foot and mouth disease", "Black quarter", "Heartwater"):
        assert t in segs, segs
    d = S.drafts_from_text(BOOK, "maize", "en", "guide.pdf")
    titles = [next(iter(x["title"].values())) for x in d]
    assert "SIGNS AND" not in titles and not any("possible" in t.lower() for t in titles)
    an = [x for x in d if x["title"]["en"] == "Anthrax"][0]["sections"]["en"]
    assert "Sudden death" in an["signs"] and an["treatment"] == ["Do not open the carcass"] and an["prevention"]

def test_book_without_clear_host_sections_is_flagged_not_labelled():
    d = S.drafts_from_text(BOOK, "maize", "en", "guide.pdf", split_hosts=D.split_document_by_hosts)
    assert len(d) >= 4 and all(x["needs_host_review"] for x in d)
    assert {x["host_key"] for x in d} == {"maize"}                  # stray "Cattle" line did NOT relabel the book

def test_single_header_in_title_area_still_counts():
    d = D.split_document_by_hosts("Tomato\nLate blight\nSigns: spots\n", "maize")
    assert d[0]["host_key"] == "tomato"

def test_publish_blocked_until_host_confirmed():
    d = S.drafts_from_text(BOOK, "maize", "en", "guide.pdf", split_hosts=D.split_document_by_hosts)[0]
    p = store.add_procedure(d)
    try:
        store.publish_procedure(p["id"], approved_by="Dr B")
        assert False, "must refuse"
    except ValueError as e:
        assert "Confirm the crop/animal" in str(e)
    store.update_procedure(p["id"], {"host_key": "cattle"})
    assert store.publish_procedure(p["id"], approved_by="Dr B")["host_key"] == "cattle"
