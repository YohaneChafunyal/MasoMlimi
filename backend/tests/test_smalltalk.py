import pytest
from app import kb_engine as K, memory as M, chat_service as CS, structure as S

CRIT = {"en": ["Isolate the animal."], "ny": ["Patulani chiweto."]}
crit = lambda l: CRIT.get(l, CRIT["en"])
PROC = [{"id": "p1", "host_key": "tomato", "status": "published", "title": {"en": "Late blight"},
         "steps": {"en": ["Remove and burn infected plants"]}, "prevention_steps": {"en": ["Sign: dark water-soaked spots on leaves"]},
         "products": [], "updated_at": "2026-01-01T00:00:00Z"}]
IDX = K.Index(PROC, 1)
ask = lambda m, lang="en", host="tomato": K.answer(IDX, m, lang, host, critical_steps=crit)

@pytest.mark.parametrize("lang,msg", [
    ("en", "Hello"), ("en", "good morning!"), ("ny", "Moni"), ("ny", "Muli bwanji?"), ("ny", "Mwadzuka bwanji"),
    ("sw", "Habari"), ("sw", "Hujambo"), ("fr", "Bonjour"), ("fr", "Salut !"), ("pt", "Olá"), ("pt", "Bom dia"),
])
def test_greetings_every_language_get_localized_reply(lang, msg):
    r = ask(msg, lang)
    assert r["outcome"] == "smalltalk" and r["reply"] == K.UI[lang]["hello"] and not r["referral_required"]

def test_greeting_works_even_if_farmer_types_another_supported_language():
    assert ask("Bonjour", "ny")["reply"] == K.UI["ny"]["hello"]          # reply stays in the CHOSEN language

@pytest.mark.parametrize("msg,key", [("thank you", "thanks_reply"), ("Zikomo kwambiri", "thanks_reply"), ("Asante", "thanks_reply"),
                                     ("merci", "thanks_reply"), ("obrigado", "thanks_reply"), ("goodbye", "bye_reply"),
                                     ("kwaheri", "bye_reply"), ("who are you", "about"), ("what can you do", "about"),
                                     ("okay", "okay_reply"), ("sawa", "okay_reply")])
def test_thanks_bye_about_okay(msg, key):
    r = ask(msg, "en")
    assert r["outcome"] == "smalltalk" and r["reply"] == K.UI["en"][key]

def test_greeting_plus_question_answers_the_question_with_a_hello():
    r = ask("Hello, dark water soaked spots on my leaves")
    assert r["outcome"] == "answer" and r["reply"].startswith("Hello!") and "Remove and burn" in r["reply"]
    r2 = ask("Moni, dark water soaked spots", "ny")
    assert r2["outcome"] == "answer" and r2["reply"].startswith("Moni!")

def test_emergency_beats_greeting():
    r = ask("hello my cow may have anthrax", "en", host="cattle")
    assert r["emergency"] and "Isolate" in r["reply"]

def test_greeting_never_becomes_a_symptom_or_a_guess():
    assert ask("hello hello")["outcome"] == "smalltalk"
    assert ask("my goat sings opera")["outcome"] == "not_sure"

def test_help_with_a_real_problem_is_not_small_talk():
    assert ask("help my tomato leaves have dark water soaked spots")["outcome"] == "answer"

def test_pack_ships_intents_and_all_languages_have_all_talk_strings():
    pack = K.build_pack(PROC, CRIT, 1)
    assert "greeting" in pack["intents"]
    for l in K.LANGS:
        for k in ("hello", "hello_short", "thanks_reply", "bye_reply", "about", "okay_reply"):
            assert pack["ui"][l][k]

def test_small_talk_is_not_recorded_as_a_case(tmp_path):
    M.reset_for_tests(tmp_path)
    class St:
        CRITICAL = CRIT
        def list_procedures(self, include_draft=False): return PROC
        def content_version(self): return 1
        def critical_steps(self, l): return crit(l)
        def normalize_host_key(self, h): return h
        def resolve_condition_bundle(self, *a, **k): return {"bundles": []}
    K._CACHE.update(v=None, idx=None)
    r = CS.chat(St(), {"message": "Hello", "language": "en", "host_key": "tomato", "device_id": "dev-12345678"})
    assert r["outcome"] == "smalltalk" and "case_id" not in r
    assert M.dashboard()["total_scans"] == 0
