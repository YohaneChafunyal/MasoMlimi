from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_critical_refer():
    r = client.post(
        "/v1/diagnosis/diagnose",
        json={
            "host_key": "cattle",
            "organism_hint": "livestock",
            "danger_signs_present": True,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["outcome"] == "critical_refer"
    assert data["products"] == []
    assert data["referral_required"] is True


def test_crop_ask_expert_no_doses():
    r = client.post(
        "/v1/diagnosis/diagnose",
        json={"host_key": "maize", "organism_hint": "crop", "answers": {"part": "leaf"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["products"] == []
    assert "procedure_steps" in data


def test_outbreak_hotspot_flow():
    r = client.post(
        "/v1/district/outbreaks",
        json={
            "organism_type": "crop",
            "host_key": "maize",
            "district": "Lilongwe",
            "ward": "Area 25",
            "country_code": "MW",
        },
    )
    assert r.status_code == 200
    oid = r.json()["id"]
    r2 = client.post(f"/v1/district/outbreaks/{oid}/review", json={"confirmed": True})
    assert r2.status_code == 200
    s = client.get("/v1/district/summary").json()
    assert s["confirmed"] >= 1
    assert any(h["ward"] == "Area 25" for h in s["outbreak_hotspots"])


def test_sync():
    r = client.post("/v1/sync/delta", json={"cursor": 0, "country": "MW", "district": "Lilongwe"})
    assert r.status_code == 200
    assert "experts" in r.json()
