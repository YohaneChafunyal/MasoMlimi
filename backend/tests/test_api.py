import io, json
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app import main, memory, store, kb_engine

KEY = {"X-API-Key": "test-key-123"}
DEV = "11111111-2222-3333-4444-555555555555"
DEV2 = "99999999-2222-3333-4444-555555555555"
DOC = b"""Late blight
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

@pytest.fixture(scope="module")
def c():
    return TestClient(main.app)

def jpeg():
    b = io.BytesIO(); Image.new("RGB", (64, 64), (30, 120, 40)).save(b, "JPEG"); return b.getvalue()

def upload(c, host="tomato", name="vet_guide.txt", data=DOC):
    return c.post("/v1/library/upload", headers=KEY, data={"host_key": host, "organism_type": "crop", "lang": "en"},
                  files=[("files", (name, data, "text/plain"))])

def test_expert_endpoints_need_key(c):
    assert c.post("/v1/procedures/x/publish").status_code == 401
    assert c.get("/v1/procedures?drafts=true").status_code == 401
    assert c.post("/v1/library/upload", files=[("files", ("a.txt", b"x", "text/plain"))]).status_code == 401
    assert c.get("/v1/chat/threads").status_code == 401
    assert c.get("/v1/dashboard/stats").status_code == 401
    assert c.get("/v1/procedures?drafts=true", headers={"X-API-Key": "wrong"}).status_code == 401

def test_upload_creates_one_draft_per_condition_hidden_from_farmers(c):
    r = upload(c); assert r.status_code == 200, r.text
    assert r.json()["drafts_created"][0]["count"] == 2
    assert c.get("/v1/procedures").json()["items"] == []
    drafts = c.get("/v1/procedures?drafts=true", headers=KEY).json()["items"]
    assert {d["title"]["en"] for d in drafts} == {"Late blight", "Bacterial wilt"}
    ans = c.post("/v1/knowledge/chat", json={"message": "dark water soaked spots", "host_key": "tomato", "language": "en", "device_id": DEV})
    assert ans.json()["outcome"] == "not_sure"      # nothing published yet

def test_publish_needs_approver_and_dose_needs_source(c):
    pid = [d for d in c.get("/v1/procedures?drafts=true", headers=KEY).json()["items"] if d["title"]["en"] == "Late blight"][0]["id"]
    assert c.post(f"/v1/procedures/{pid}/publish", headers=KEY, json={}).status_code == 422
    assert c.post(f"/v1/procedures/{pid}/publish", headers=KEY, json={"approved_by": "Dr Banda", "dose_verified": True}).status_code == 422
    r = c.post(f"/v1/procedures/{pid}/publish", headers=KEY, json={"approved_by": "Dr Banda"})
    assert r.status_code == 200 and r.json()["status"] == "published"
    other = [d for d in c.get("/v1/procedures?drafts=true", headers=KEY).json()["items"] if d["title"]["en"] == "Bacterial wilt"][0]["id"]
    c.post(f"/v1/procedures/{other}/publish", headers=KEY, json={"approved_by": "Dr Banda"})

def test_chat_without_verified_dose_hides_it_then_shows_after_vet_verifies(c):
    ask = lambda dev=DEV: c.post("/v1/knowledge/chat", json={"message": "dark water soaked spots on leaves", "host_key": "tomato", "language": "en", "device_id": dev, "district": "Lilongwe"}).json()
    a = ask()
    assert a["outcome"] == "answer" and "Remove and burn" in a["reply"] and "2 g per litre" not in a["reply"]
    pid = a["procedure_ids"][0]
    r = c.post(f"/v1/procedures/{pid}/publish", headers=KEY, json={"approved_by": "Dr Banda", "dose_verified": True, "dose_source": "Official register 2025"})
    assert r.status_code == 200
    b = ask()
    assert "2 g per litre" in b["reply"] and "Official register 2025" in b["reply"]

def test_editing_published_content_sends_it_back_to_draft(c):
    pid = [p for p in store.list_procedures() if p["title"]["en"] == "Bacterial wilt"][0]["id"]
    r = c.put(f"/v1/procedures/{pid}", headers=KEY, json={"title": {"en": "Bacterial wilt"}, "steps": {"en": ["Uproot and burn"]}})
    assert r.json()["status"] == "draft"
    assert all(p["id"] != pid for p in c.get("/v1/procedures").json()["items"])
    c.post(f"/v1/procedures/{pid}/publish", headers=KEY, json={"approved_by": "Dr Banda"})

def test_farmer_cannot_impersonate_expert_and_reply_to_works(c):
    x = "officer-1"
    m1 = c.post("/v1/chat", json={"device_id": DEV, "expert_id": x, "text": "my goat is weak", "client_id": "c1"}).json()
    assert c.post("/v1/chat", json={"device_id": DEV, "expert_id": x, "text": "fake", "sender": "expert"}).status_code == 401
    m2 = c.post("/v1/chat", headers=KEY, json={"device_id": DEV, "expert_id": x, "text": "how old?", "sender": "expert", "reply_to": m1["id"]}).json()
    assert m2["reply_preview"]["text"] == "my goat is weak" and m2["reply_to"] == m1["id"]
    again = c.post("/v1/chat", json={"device_id": DEV, "expert_id": x, "text": "my goat is weak", "client_id": "c1"}).json()
    assert again["id"] == m1["id"]                                         # idempotent retry
    audio = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 700
    v = c.post("/v1/chat/voice", data={"device_id": DEV, "expert_id": x, "sender": "farmer", "client_id": "v1", "reply_to": m2["id"]},
               files={"audio": ("n.m4a", audio, "audio/mp4")}).json()
    assert v["type"] == "audio_note" and v["reply_preview"]["text"] == "how old?"
    q = c.post("/v1/chat", json={"device_id": DEV, "expert_id": x, "text": "re voice", "reply_to": v["id"]}).json()
    assert q["reply_preview"]["type"] == "audio_note"
    name = v["text"][len("[voice_note:"):-1]
    assert c.get(f"/v1/chat/voice/{name}").status_code == 200
    assert c.get("/v1/chat/voice/..%2F..%2Fetc%2Fpasswd").status_code in (404, 422)
    assert c.get("/v1/chat/voice/notvalid.m4a").status_code == 404

def test_bad_uploads_rejected(c):
    assert c.post("/v1/chat/voice", data={"device_id": DEV, "expert_id": "o"}, files={"audio": ("n.m4a", b"A" * 900, "audio/mp4")}).status_code == 415
    r = c.post("/v1/library/upload", headers=KEY, files=[("files", ("evil.pdf", b"MZ" + b"\x00" * 100, "application/pdf"))])
    assert r.status_code == 415
    assert c.post("/v1/chat", json={"device_id": "../x", "expert_id": "o", "text": "hi"}).status_code == 422

def test_scan_photo_and_validation(c):
    ok = c.post("/v1/scan/analyze", data={"host_key": "tomato", "organism_hint": "crop", "language": "en", "device_id": DEV2,
                "symptom_keys": json.dumps(["spots"]), "notes": "dark water soaked"}, files={"image": ("p.jpg", jpeg(), "image/jpeg")})
    assert ok.status_code == 200, ok.text
    j = ok.json(); assert j["outcome"] == "answer" and j["case_id"] and j["ml"]["certified"] is False
    assert c.post("/v1/scan/analyze", data={"host_key": "tomato"}, files={"image": ("p.jpg", b"notimage" * 20, "image/jpeg")}).status_code == 415
    red = c.post("/v1/scan/analyze", data={"host_key": "goats", "organism_hint": "livestock", "language": "ny", "symptom_keys": json.dumps(["sudden_many_dead"])},
                 files={"image": ("p.jpg", jpeg(), "image/jpeg")}).json()
    assert red["outcome"] == "emergency" and red["result_color"] == "red" and "Patulani" in red["reply"]

def test_feedback_dashboard_and_privacy(c):
    j = c.post("/v1/knowledge/chat", json={"message": "dark water soaked spots", "host_key": "tomato", "device_id": DEV2}).json()
    assert c.post("/v1/memory/feedback", json={"case_id": j["case_id"], "helped": "yes"}).status_code == 200
    assert c.post("/v1/memory/feedback", json={"case_id": "zz", "helped": "yes"}).status_code == 422
    d = c.get("/v1/dashboard/stats", headers=KEY).json()
    assert d["stats"]["total_scans"] >= 3 and "dev" not in json.dumps(d)
    assert c.post("/v1/memory/delete-my-data", json={"device_id": DEV2}).json()["cases_deleted"] >= 1

def test_library_files_not_public_unless_published_image(c):
    items = c.get("/v1/library", headers=KEY).json()["items"]
    sn = items[0]["stored_name"]
    assert c.get(f"/v1/library/file/{sn}").status_code == 401          # source documents need the key
    assert c.get(f"/v1/library/file/{sn}", headers=KEY).status_code == 200
    assert all("extracted_text" not in i for i in c.get("/v1/library").json()["items"])

def test_chatpack_and_sync_expose_only_published(c):
    pack = c.get("/v1/sync/chatpack").json()
    assert len(pack["procedures"]) == 2 and pack["signature"]
    assert "memory" not in c.get("/v1/sync/knowledge").json()

def test_cors_not_wildcard_and_headers(c):
    r = c.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"

def test_chat_at_rest_encrypted(c):
    raw = (store._DATA_DIR / "chats.json").read_text()
    assert raw.startswith("enc:") and "my goat is weak" not in raw

def test_rate_limit_scan(c):
    codes = [c.post("/v1/scan/analyze", data={"host_key": "tomato"}, files={"image": ("p.jpg", b"x", "image/jpeg")}).status_code for _ in range(16)]
    assert 429 in codes

def test_auth_lockout(c):
    codes = [c.get("/v1/pilot/status", headers={"X-API-Key": "bad"}).status_code for _ in range(14)]
    assert 429 in codes

def test_portal_served_with_csp_and_no_inline_data_injection(c):
    r = c.get("/portal/")
    assert r.status_code == 200 and "MasoMlimi Expert Portal" in r.text
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "innerHTML" not in r.text            # farmer-supplied text is never rendered as HTML
