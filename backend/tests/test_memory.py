import pytest
from app import memory as M

@pytest.fixture(autouse=True)
def fresh(tmp_path):
    M.reset_for_tests(tmp_path)

def case(dev, toks=("spot","leave","dark"), proc="p0", outcome="answer", host="tomato", dist="Lilongwe", fb=None):
    c = M.record_case(dev, host, dist, list(toks), proc, outcome, "high", 0.8)
    if fb: M.feedback(c["id"], fb)
    return c

def test_similar_counts_distinct_devices_and_excludes_self():
    for d in ("a","b","c","d"): case(d)
    s = M.similar("tomato", ["spot","leave"], district="Lilongwe", exclude_dev="a")
    assert s["farmers"] == 3 and s["cases"] == 3
    assert M.similar("maize", ["spot","leave"])["farmers"] == 0

def test_prior_only_from_helpful_answered_cases():
    case("a"); case("b")
    assert M.prior("tomato", ["spot","leave","dark"]) == {}
    case("c", fb="yes"); case("d", fb="no")
    p = M.prior("tomato", ["spot","leave","dark"])
    assert set(p) == {"p0"} and 0 < p["p0"] <= 1

def test_alias_suggestions_need_k_devices_and_expert_approval():
    known = lambda pid: {"spot","leave"}
    for d in ("a","b","c"):
        c = M.record_case(d, "tomato", "L", ["spot","mafunde"], "p0", "answer", "high", .8)
        M.feedback(c["id"], "yes", known)
    s = M.suggestions()
    assert s and s[0]["token"] == "mafunde" and s[0]["farmers"] == 3
    assert M.approved_aliases() == {}
    assert M.approve_alias("p0", "mafunde") and M.approved_aliases() == {"p0": ["mafunde"]}

def test_nearby_and_trends_respect_k():
    for d in ("a","b"): case(d)
    assert M.trends("Lilongwe") == []
    case("c")
    assert M.trends("Lilongwe")[0]["farmers"] == 3

def test_delete_my_data_and_photo_hint():
    c = M.record_case("a","tomato","L",["x"],"p0","answer","high",.8,photo="ffffffffffffffff")
    case("b")
    assert M.photo_matches("tomato","fffffffffffffffe", exclude_dev="z")["farmers"] == 1
    assert M.delete_device("a") == 1 and M.photo_matches("tomato","ffffffffffffffff")["farmers"] == 0
