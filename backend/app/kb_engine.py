"""MasoMlimi grounded chat engine (replaces store.kb_chat_reply for /v1/knowledge/chat).

Design rules (see SAFETY.md):
  * Answers are built ONLY from procedures with status == "published". The engine never writes
    advice. Library files that are not linked to a published procedure are never used.
  * Dangerous / reportable diseases and livestock danger signs are handled by FIXED rules here.
    No language model and no retrieved text can change that path.
  * Doses, application rates and withdrawal times are redacted unless a procedure carries
    dose_verified=True (expert + official citation). Otherwise: "ask a vet or agro-dealer".
  * Below the confidence threshold the answer is "not sure, ask an expert". Never a guess.
  * Replies come in the farmer's language when a translation exists. Otherwise the engine
    falls back to the source text, SAYS SO in the farmer's language, and (optionally) lets a
    language model translate it, flagged as machine-translated and number-verified.

LAUNCH GATES: UI strings and LEXICON are machine-drafted -> native-speaker review required.
MIN_COVERAGE must be calibrated on an expert-labelled question set before production.
"""
from __future__ import annotations

import math
import os
import re
import unicodedata
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

LANGS = ("en", "ny", "fr", "sw", "pt")
LIVESTOCK = {"chicken", "goats", "cattle", "pigs", "sheep", "ducks"}
MIN_COVERAGE = float(os.environ.get("MASOMLIMI_CHAT_MIN_COVERAGE", "0.34"))
HIGH_COVERAGE = float(os.environ.get("MASOMLIMI_CHAT_HIGH_COVERAGE", "0.60"))
AMBIGUITY_RATIO = 0.85
UI_REVIEW_STATUS = "needs_native_review"

# ----------------------------------------------------------------------------- UI strings
UI: Dict[str, Dict[str, str]] = {
    "en": {
        "from_library": "From the approved expert library",
        "signs": "Signs", "steps": "What to do", "prevention": "Prevention",
        "products": "Products (as published)", "source": "Source", "approved": "Approved",
        "not_sure": "I am not sure about this. Please ask an expert. I will not guess.",
        "ask_expert": "Ask a vet, extension officer or agro-dealer before using any medicine or chemical.",
        "dose_ask": "Doses and application rates are not given here. Ask a vet or agro-dealer to confirm.",
        "chem_note": "This involves a medicine or strong chemical - ask an expert first.",
        "lang_fallback": "This guidance is not yet available in your language. Showing the original.",
        "machine_translated": "Machine-translated - not yet checked by a native-speaking expert.",
        "translation_unreviewed": "Translation is waiting for expert review.",
        "emergency_title": "This may be a serious or reportable disease. Do not treat at home.",
        "emergency_expert": "Contact the nearest verified vet or district office now.",
        "did_you_mean": "Which of these do you mean?",
        "list_title": "Approved conditions for {h}",
        "none_for_host": "No approved guidance for {h} yet. Please ask an expert.",
        "empty_query": "Please tell me what you see on the plant or animal.",
        "conf_high": "Good match", "conf_medium": "Possible match", "conf_low": "Not sure",
    },
    "ny": {
        "from_library": "Kuchokera ku buku la akatswiri lovomerezeka",
        "signs": "Zizindikiro", "steps": "Zoyenera kuchita", "prevention": "Kupewa",
        "products": "Mankhwala (monga zasindikizidwa)", "source": "Gwero", "approved": "Zavomerezedwa",
        "not_sure": "Sindikudziwa bwino za izi. Chonde funsani katswiri. Sindingangoganiza.",
        "ask_expert": "Funsani vet, extension officer kapena wogulitsa mankhwala musanagwiritse ntchito mankhwala.",
        "dose_ask": "Kuchuluka kwa mankhwala sikuperekedwa pano. Funsani vet kapena wogulitsa mankhwala kuti atsimikize.",
        "chem_note": "Ili ndi mankhwala amphamvu - funsani katswiri poyamba.",
        "lang_fallback": "Uphungu uwu sunapezeke m'chilankhulo chanu. Mukuona choyambirira.",
        "machine_translated": "Kumasuliridwa ndi makina - sikunawunikidwe ndi katswiri.",
        "translation_unreviewed": "Kumasulira kukudikira kuwunikidwa ndi katswiri.",
        "emergency_title": "Ichi chikhoza kukhala matenda oopsa. Musachize kunyumba.",
        "emergency_expert": "Lumikizanani ndi vet kapena ofesi ya boma tsopano.",
        "did_you_mean": "Mukutanthauza chiti mwa izi?",
        "list_title": "Matenda ovomerezeka a {h}",
        "none_for_host": "Palibe uphungu wovomerezeka wa {h} pano. Chonde funsani katswiri.",
        "empty_query": "Chonde ndiuzeni zomwe mukuona pa mbewu kapena chiweto.",
        "conf_high": "Zikugwirizana bwino", "conf_medium": "Mwina zikugwirizana", "conf_low": "Sindikutsimikiza",
    },
    "fr": {
        "from_library": "Issu de la bibliothèque d'experts approuvée",
        "signs": "Signes", "steps": "Que faire", "prevention": "Prévention",
        "products": "Produits (tels que publiés)", "source": "Source", "approved": "Approuvé",
        "not_sure": "Je ne suis pas sûr. Demandez à un expert. Je ne devine pas.",
        "ask_expert": "Demandez à un vétérinaire, un agent de vulgarisation ou un revendeur avant tout médicament ou produit chimique.",
        "dose_ask": "Les doses et taux d'application ne sont pas donnés ici. Demandez confirmation à un vétérinaire ou un revendeur.",
        "chem_note": "Cela concerne un médicament ou un produit chimique fort - demandez d'abord à un expert.",
        "lang_fallback": "Ce conseil n'est pas encore disponible dans votre langue. Affichage de l'original.",
        "machine_translated": "Traduit automatiquement - pas encore vérifié par un expert locuteur natif.",
        "translation_unreviewed": "Traduction en attente de vérification par un expert.",
        "emergency_title": "Il peut s'agir d'une maladie grave ou à déclaration obligatoire. Ne traitez pas à la maison.",
        "emergency_expert": "Contactez dès maintenant le vétérinaire ou le bureau de district le plus proche.",
        "did_you_mean": "Lequel voulez-vous dire ?",
        "list_title": "Affections approuvées pour {h}",
        "none_for_host": "Pas encore de conseil approuvé pour {h}. Demandez à un expert.",
        "empty_query": "Dites-moi ce que vous voyez sur la plante ou l'animal.",
        "conf_high": "Bonne correspondance", "conf_medium": "Correspondance possible", "conf_low": "Pas sûr",
    },
    "sw": {
        "from_library": "Kutoka maktaba ya wataalamu iliyoidhinishwa",
        "signs": "Ishara", "steps": "Cha kufanya", "prevention": "Kinga",
        "products": "Bidhaa (kama zilivyochapishwa)", "source": "Chanzo", "approved": "Imeidhinishwa",
        "not_sure": "Sina uhakika. Tafadhali muulize mtaalamu. Sitabahatisha.",
        "ask_expert": "Muulize daktari wa mifugo, afisa ugani au muuzaji wa pembejeo kabla ya kutumia dawa au kemikali yoyote.",
        "dose_ask": "Kipimo na kiasi cha kutumia hakitolewi hapa. Muulize daktari wa mifugo au muuzaji wa pembejeo athibitishe.",
        "chem_note": "Hii inahusu dawa au kemikali kali - muulize mtaalamu kwanza.",
        "lang_fallback": "Mwongozo huu bado haupatikani kwa lugha yako. Unaonyeshwa wa asili.",
        "machine_translated": "Imetafsiriwa na mashine - bado haijakaguliwa na mtaalamu.",
        "translation_unreviewed": "Tafsiri inasubiri ukaguzi wa mtaalamu.",
        "emergency_title": "Huu unaweza kuwa ugonjwa mkubwa au wa kuripotiwa. Usitibu nyumbani.",
        "emergency_expert": "Wasiliana na daktari wa mifugo au ofisi ya wilaya sasa.",
        "did_you_mean": "Unamaanisha ipi kati ya hizi?",
        "list_title": "Magonjwa yaliyoidhinishwa ya {h}",
        "none_for_host": "Bado hakuna mwongozo ulioidhinishwa wa {h}. Muulize mtaalamu.",
        "empty_query": "Tafadhali niambie unachoona kwenye mmea au mnyama.",
        "conf_high": "Inalingana vizuri", "conf_medium": "Inawezekana", "conf_low": "Sina uhakika",
    },
    "pt": {
        "from_library": "Da biblioteca de especialistas aprovada",
        "signs": "Sinais", "steps": "O que fazer", "prevention": "Prevenção",
        "products": "Produtos (como publicado)", "source": "Fonte", "approved": "Aprovado",
        "not_sure": "Não tenho certeza. Pergunte a um especialista. Não vou adivinhar.",
        "ask_expert": "Pergunte a um veterinário, técnico de extensão ou revendedor antes de usar qualquer medicamento ou produto químico.",
        "dose_ask": "Doses e taxas de aplicação não são dadas aqui. Peça a um veterinário ou revendedor para confirmar.",
        "chem_note": "Isto envolve um medicamento ou produto químico forte - pergunte primeiro a um especialista.",
        "lang_fallback": "Esta orientação ainda não está disponível no seu idioma. A mostrar o original.",
        "machine_translated": "Traduzido automaticamente - ainda não verificado por um especialista nativo.",
        "translation_unreviewed": "Tradução à espera de revisão por especialista.",
        "emergency_title": "Pode ser uma doença grave ou de notificação obrigatória. Não trate em casa.",
        "emergency_expert": "Contacte agora o veterinário ou o posto distrital mais próximo.",
        "did_you_mean": "Qual destes quer dizer?",
        "list_title": "Condições aprovadas para {h}",
        "none_for_host": "Ainda sem orientação aprovada para {h}. Pergunte a um especialista.",
        "empty_query": "Diga-me o que vê na planta ou no animal.",
        "conf_high": "Boa correspondência", "conf_medium": "Possível correspondência", "conf_low": "Sem certeza",
    },
}

# ----------------------------------------------------------------------------- language data
_STOP = set("""
the a an is are was were of to and in on at my our your what how do does did i it its this that these those
with for have has had can could should would will why when where which who me we you they them there here be been
please help advice tell about some any very also not no yes or if as from by okay ok thanks thank hello hi
le la les un une des de du et est je mon ma mes que quoi comment pour avec sur dans au aux ce cette ces
o os as um uma uns umas do da dos das e eu meu minha que como para com em no na nos nas
na ya wa kwa ni la za katika yangu je kwamba hii huu hiki
ndi ku mu nga wa za la ya mwa kuti
""".split())

# word (accent-folded, apostrophes removed) -> canonical English token. NEEDS NATIVE REVIEW.
LEXICON: Dict[str, str] = {
    # English irregulars
    "leaf": "leaves", "diarrhoea": "diarrhea", "loosestool": "diarrhea", "maggots": "worm", "caterpillars": "caterpillar",
    # Swahili
    "majani": "leaves", "jani": "leaves", "madoa": "spots", "doa": "spots", "kuhara": "diarrhea",
    "kikohozi": "cough", "homa": "fever", "kunyauka": "wilt", "mizizi": "roots", "mzizi": "roots",
    "wadudu": "insects", "mdudu": "insects", "ugonjwa": "disease", "magonjwa": "disease", "dawa": "medicine",
    "kinga": "prevention", "matibabu": "treatment", "ishara": "signs", "dalili": "signs",
    "njano": "yellow", "kuoza": "rot", "dhaifu": "weak", "minyoo": "worm", "kupe": "tick",
    # French
    "feuilles": "leaves", "feuille": "leaves", "taches": "spots", "tache": "spots", "diarrhee": "diarrhea",
    "toux": "cough", "fievre": "fever", "fletrissement": "wilt", "fletri": "wilt", "racines": "roots",
    "racine": "roots", "insectes": "insects", "insecte": "insects", "maladie": "disease", "maladies": "disease",
    "medicament": "medicine", "medicaments": "medicine", "prevention": "prevention", "traitement": "treatment",
    "signes": "signs", "jaune": "yellow", "jaunes": "yellow", "jaunissement": "yellow", "pourriture": "rot",
    "faible": "weak", "vers": "worm", "tiques": "tick", "tique": "tick",
    # Portuguese
    "folhas": "leaves", "folha": "leaves", "manchas": "spots", "mancha": "spots", "diarreia": "diarrhea",
    "tosse": "cough", "febre": "fever", "murcha": "wilt", "murchas": "wilt", "raizes": "roots", "raiz": "roots",
    "insetos": "insects", "inseto": "insects", "doenca": "disease", "doencas": "disease", "remedio": "medicine",
    "medicamento": "medicine", "prevencao": "prevention", "tratamento": "treatment", "sinais": "signs",
    "amarelo": "yellow", "amarelas": "yellow", "amarelas": "yellow", "podridao": "rot", "fraco": "weak",
    "vermes": "worm", "carrapatos": "tick", "carrapato": "tick",
    # Chichewa
    "masamba": "leaves", "tsamba": "leaves", "mawanga": "spots", "matenda": "disease", "mankhwala": "medicine",
    "tizilombo": "insects", "kachilombo": "insects", "kutsokomola": "cough", "kufota": "wilt",
    "achikasu": "yellow", "chikasu": "yellow", "kuvunda": "rot", "kupewa": "prevention",
    "chithandizo": "treatment", "zizindikiro": "signs",
}

DANGER_TERMS = [
    "anthrax", "charbon", "carbunculo", "kimeta",
    "foot and mouth", "foot and mouth disease", "fmd", "fievre aphteuse", "febre aftosa",
    "east coast fever", "ndigana kali", "newcastle", "kideri",
    "african swine fever", "peste porcine africaine", "peste suina africana",
    "rift valley", "homa ya bonde la ufa", "rabies", "rage", "raiva", "kichaa cha mbwa",
]
DANGER_SIGNS = [
    "sudden death", "sudden deaths", "died suddenly", "many died", "many dead", "bleeding", "blood from", "bloody",
    "cannot stand", "unable to stand", "mort subite", "meurent", "saignement", "sang", "ne peut pas se lever",
    "morte subita", "morreram", "sangramento", "sangue", "nao consegue ficar de pe",
    "kifo cha ghafla", "wamekufa wengi", "damu", "hawezi kusimama",
    "kufa mwadzidzidzi", "zambiri zafa", "magazi", "sangathe kuyimirira",
]

_DOSE = re.compile(
    r"(\d+([.,]\d+)?\s*(ml|mg|g|kg|l|cc|iu|ppm|litres?|liters?|tablets?|tabs?|sachets?|capsules?|spoons?|"
    r"teaspoons?|tablespoons?|tsp|tbsp|drops?|doses?)\b)|(\d+([.,]\d+)?\s*%)"
    r"|(\bper\s+(litre|liter|hectare|acre|kg|animal|bird|head|plant|tank|knapsack)\b)"
    r"|(\b(dose|doses|dosage|dosing|dosagem|posologie|kipimo|withdrawal)\b)|(\bmg\s*/\s*kg\b)|(\bml\s*/\s*l\b)",
    re.I)
_DOSE_Q = ["dose", "dosage", "dosagem", "posologie", "kipimo", "kiasi", "kuchuluka", "how much", "combien",
           "quanto", " ml ", " mg ", "withdrawal", "spray rate"]
_CHEM = re.compile(
    r"antibiotic|antibiotique|antibiotico|tetracycline|penicillin|streptomycin|sulfa|ivermectin|albendazole|"
    r"levamisole|pesticide|insecticide|fungicide|herbicide|acaricide|\bdip\b|\bspray|cypermethrin|mancozeb|"
    r"dimethoate|chemical|chimique|quimico|kemikali|mankhwala amphamvu", re.I)
_PLACEHOLDER = re.compile(r"^\s*(expert review required|draft|do not use as treatment|do not show to farmers|this is a draft)", re.I)
_JUNK = ("inside this guide", "table of contents", "how to use this guide", "educational guide", "page ",
         "african livestock and crop", "quick symptom lookup", "part a -", "part b -", "consult a vet",
         "follow product labels")
_LIST_WORDS = ["types of", "list", "which diseases", "what diseases", "all diseases", "what are", "conditions of",
               "problems of", "pests of", "matenda a", "magonjwa ya", "maladies de", "doencas de", "quelles maladies"]


# ----------------------------------------------------------------------------- text helpers
def _fold(s: str) -> str:
    s = (s or "").lower().replace("\u2019", "'").replace("\u0153", "oe")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("'", "")


def _plain(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _fold(s)).strip()


def _stem(t: str) -> str:
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 5 and t.endswith(("ches", "shes", "xes", "sses")):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        t = t[:-1]
    if len(t) > 5 and t.endswith("ing"):
        return t[:-3]
    if len(t) > 5 and t.endswith("ed"):
        return t[:-2]
    return t


def tokens(s: str) -> List[str]:
    out = []
    for t in re.findall(r"[a-z0-9]+", _fold(s)):
        if len(t) < 2 or t in _STOP:
            continue
        out.append(_stem(LEXICON.get(t, t)))
    return out


def _has_phrase(plain: str, phrase: str) -> bool:
    return f" {_plain(phrase)} " in f" {plain} "


def clean_user_text(s: str, limit: int = 600) -> str:
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", str(s or ""))
    return re.sub(r"\s+", " ", s).strip()[:limit]


def _facts(text: str) -> List[str]:
    out, seen = [], set()
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        s = sent.strip()
        low = s.lower()
        if not (25 <= len(s) <= 400) or any(j in low for j in _JUNK):
            continue
        if s.count("|") >= 2 or low in seen:
            continue
        seen.add(low)
        out.append(s)
        if len(out) >= 60:
            break
    return out


def _clean_line(line: str) -> str:
    s = re.sub(r"^\s*signs?\s*:\s*", "", str(line or ""), flags=re.I)
    s = re.sub(r"^\s*(?:[\-\*\u2022\u25cf]\s*)*(?:\d+[.)]\s+)?", "", s).strip()   # list markers only; never real numbers
    s = re.sub(r"\s+", " ", s)
    if len(s) > 220:
        s = s[:220].rsplit(" ", 1)[0] + "..."
    return s


def _is_dangerous(p: dict) -> bool:
    if p.get("is_dangerous") or p.get("reportable") or p.get("zoonotic"):
        return True
    names = _plain(" ".join(str(v) for v in (p.get("title") or {}).values()))
    return any(_has_phrase(names, t) for t in DANGER_TERMS)


# ----------------------------------------------------------------------------- extra UI strings
_UI2 = {
    "en": {"symptoms": "Symptoms", "medicines": "Medicines and products",
           "dose_label": "Dose and withdrawal (as published by the vet)", "refer": "When to get help",
           "type_label": "Type", "t_disease": "disease", "t_pest": "pest", "t_nutrient": "nutrient problem",
           "t_parasite": "parasite", "dose_source": "Dose source",
           "follow_label": "Follow the product label and ask a vet or agro-dealer if unsure.",
           "similar_seen": "{n} other farmers near you asked about a similar problem in the last {d} days.",
           "feedback_q": "Did this advice help?", "fb_yes": "Yes, it helped", "fb_no": "No"},
    "ny": {"symptoms": "Zizindikiro zina", "medicines": "Mankhwala",
           "dose_label": "Kuchuluka ndi nthawi yodikira (monga katswiri wasindikiza)", "refer": "Nthawi yofuna thandizo",
           "type_label": "Mtundu", "t_disease": "matenda", "t_pest": "tizilombo toononga",
           "t_nutrient": "kusowa kwa michere", "t_parasite": "tiziromboti", "dose_source": "Gwero la kuchuluka",
           "follow_label": "Tsatirani malangizo pa chidebe ndipo funsani vet kapena wogulitsa ngati simukutsimikiza.",
           "similar_seen": "Alimi ena {n} pafupi nanu anafunsa za vuto lofanana m'masiku {d} apitawa.",
           "feedback_q": "Kodi uphungu uwu wakuthandizani?", "fb_yes": "Inde, wandithandiza", "fb_no": "Ayi"},
    "fr": {"symptoms": "Symptômes", "medicines": "Médicaments et produits",
           "dose_label": "Dose et délai d'attente (tels que publiés par le vétérinaire)", "refer": "Quand demander de l'aide",
           "type_label": "Type", "t_disease": "maladie", "t_pest": "ravageur", "t_nutrient": "trouble nutritif",
           "t_parasite": "parasite", "dose_source": "Source de la dose",
           "follow_label": "Suivez l'étiquette du produit et demandez à un vétérinaire ou revendeur en cas de doute.",
           "similar_seen": "{n} autres agriculteurs près de chez vous ont posé une question similaire ces {d} derniers jours.",
           "feedback_q": "Ce conseil vous a-t-il aidé ?", "fb_yes": "Oui, il m'a aidé", "fb_no": "Non"},
    "sw": {"symptoms": "Dalili", "medicines": "Dawa na bidhaa",
           "dose_label": "Kipimo na muda wa kusubiri (kama ilivyochapishwa na daktari)", "refer": "Wakati wa kutafuta msaada",
           "type_label": "Aina", "t_disease": "ugonjwa", "t_pest": "mdudu mharibifu", "t_nutrient": "upungufu wa virutubisho",
           "t_parasite": "kimelea", "dose_source": "Chanzo cha kipimo",
           "follow_label": "Fuata lebo ya bidhaa na muulize daktari wa mifugo au muuzaji usipokuwa na uhakika.",
           "similar_seen": "Wakulima wengine {n} karibu nawe waliuliza tatizo linalofanana katika siku {d} zilizopita.",
           "feedback_q": "Je, ushauri huu ulisaidia?", "fb_yes": "Ndiyo, ulisaidia", "fb_no": "Hapana"},
    "pt": {"symptoms": "Sintomas", "medicines": "Medicamentos e produtos",
           "dose_label": "Dose e período de carência (como publicado pelo veterinário)", "refer": "Quando pedir ajuda",
           "type_label": "Tipo", "t_disease": "doença", "t_pest": "praga", "t_nutrient": "problema nutricional",
           "t_parasite": "parasita", "dose_source": "Fonte da dose",
           "follow_label": "Siga o rótulo do produto e pergunte a um veterinário ou revendedor se tiver dúvida.",
           "similar_seen": "{n} outros agricultores perto de si perguntaram sobre um problema parecido nos últimos {d} dias.",
           "feedback_q": "Este conselho ajudou?", "fb_yes": "Sim, ajudou", "fb_no": "Não"},
}
for _l, _d in _UI2.items():
    UI[_l].update(_d)

K_MIN_FARMERS = 3          # k-anonymity: never show "N farmers" below this
SEC_KEYS = ("signs", "symptoms", "treatment", "medication", "dose", "prevention", "refer")


# ----------------------------------------------------------------------------- small talk (fixed text, no model)
INTENTS: Dict[str, List[str]] = {
    "greeting": ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening", "how are you",
                 "moni", "muli bwanji", "mwadzuka bwanji", "mwaswera bwanji", "madzulo abwino", "odi",
                 "habari", "hujambo", "mambo", "salamu", "shikamoo", "habari za asubuhi", "habari za mchana", "habari za jioni",
                 "bonjour", "salut", "bonsoir", "coucou", "ca va", "comment allez vous", "comment ca va",
                 "ola", "oi", "bom dia", "boa tarde", "boa noite", "tudo bem", "como esta", "como vai"],
    "thanks": ["thanks", "thank you", "thank", "zikomo", "zikomo kwambiri", "asante", "asante sana", "merci", "merci beaucoup",
               "obrigado", "obrigada", "muito obrigado", "muito obrigada"],
    "bye": ["bye", "goodbye", "see you", "tsalani bwino", "pitani bwino", "kwaheri", "au revoir", "a bientot", "adeus", "ate logo", "tchau"],
    "about": ["who are you", "what can you do", "what do you do", "how does this work", "help", "ndinu ndani", "wewe ni nani",
              "unaweza kufanya nini", "qui es tu", "qui etes vous", "que pouvez vous faire", "quem es tu", "quem e voce", "o que voce faz"],
    "okay": ["ok", "okay", "alright", "sawa", "chabwino", "d accord", "daccord"],
}

_UI_TALK = {
    "en": {"hello": "Hello! I am MasoMlimi, your farm helper. Tell me what you see on your plant or animal. I answer only from advice approved by experts.",
           "hello_short": "Hello!",
           "thanks_reply": "You are welcome. Ask me anything else about your crops or animals.",
           "bye_reply": "Goodbye. Come back any time. If an animal is very sick, call a vet.",
           "about": "I help with crop and animal health. Tell me what you see, or send a photo. I answer only from advice approved by experts, and I will say so when I am not sure.",
           "okay_reply": "Okay. Tell me what you see on the plant or animal, or tap Get advice."},
    "ny": {"hello": "Moni! Ndine MasoMlimi, wothandiza wanu pa munda. Ndiuzeni zomwe mukuona pa mbewu kapena chiweto chanu. Ndimayankha pogwiritsa ntchito uphungu wovomerezeka ndi akatswiri okha.",
           "hello_short": "Moni!",
           "thanks_reply": "Zikomo. Mutha kufunsa china chilichonse chokhudza mbewu kapena ziweto zanu.",
           "bye_reply": "Tsalani bwino. Bwererani nthawi iliyonse. Ngati chiweto chadwala kwambiri, imbirani vet.",
           "about": "Ndimathandiza pa thanzi la mbewu ndi ziweto. Ndiuzeni zomwe mukuona, kapena tumizani chithunzi. Ndimayankha pogwiritsa ntchito uphungu wovomerezeka ndi akatswiri okha, ndipo ndidzanena ngati sindikutsimikiza.",
           "okay_reply": "Chabwino. Ndiuzeni zomwe mukuona pa mbewu kapena chiweto, kapena dinani Pezani uphungu."},
    "fr": {"hello": "Bonjour ! Je suis MasoMlimi, votre aide agricole. Dites-moi ce que vous voyez sur votre plante ou votre animal. Je réponds uniquement à partir de conseils approuvés par des experts.",
           "hello_short": "Bonjour !",
           "thanks_reply": "Je vous en prie. Posez-moi toute autre question sur vos cultures ou vos animaux.",
           "bye_reply": "Au revoir. Revenez quand vous voulez. Si un animal est très malade, appelez un vétérinaire.",
           "about": "J'aide pour la santé des cultures et des animaux. Dites-moi ce que vous voyez ou envoyez une photo. Je réponds uniquement à partir de conseils approuvés par des experts et je le dis quand je ne suis pas sûr.",
           "okay_reply": "D'accord. Dites-moi ce que vous voyez sur la plante ou l'animal, ou appuyez sur Obtenir des conseils."},
    "sw": {"hello": "Habari! Mimi ni MasoMlimi, msaidizi wako wa shamba. Niambie unachoona kwenye mmea au mnyama wako. Ninajibu tu kutokana na ushauri ulioidhinishwa na wataalamu.",
           "hello_short": "Habari!",
           "thanks_reply": "Karibu. Uliza chochote kingine kuhusu mazao au mifugo yako.",
           "bye_reply": "Kwaheri. Rudi wakati wowote. Mnyama akiwa mgonjwa sana, mpigie daktari wa mifugo.",
           "about": "Ninasaidia kuhusu afya ya mazao na mifugo. Niambie unachoona au tuma picha. Ninajibu tu kutokana na ushauri ulioidhinishwa na wataalamu, na nitasema nikiwa sina uhakika.",
           "okay_reply": "Sawa. Niambie unachoona kwenye mmea au mnyama, au bonyeza Pata ushauri."},
    "pt": {"hello": "Olá! Sou o MasoMlimi, o seu ajudante na quinta. Diga-me o que vê na sua planta ou animal. Respondo apenas com conselhos aprovados por especialistas.",
           "hello_short": "Olá!",
           "thanks_reply": "De nada. Pergunte o que quiser sobre as suas culturas ou animais.",
           "bye_reply": "Adeus. Volte quando quiser. Se um animal estiver muito doente, ligue a um veterinário.",
           "about": "Ajudo com a saúde das culturas e dos animais. Diga-me o que vê ou envie uma foto. Respondo apenas com conselhos aprovados por especialistas e digo quando não tenho certeza.",
           "okay_reply": "Certo. Diga-me o que vê na planta ou no animal, ou toque em Obter conselho."},
}
for _l, _d in _UI_TALK.items():
    UI[_l].update(_d)

_INTENT_KEY = {"about": "about", "greeting": "hello", "thanks": "thanks_reply", "bye": "bye_reply", "okay": "okay_reply"}


def split_intents(plain: str):
    """-> (set of intents found, the message with those phrases removed)."""
    rest = f" {plain} "
    found = set()
    items = sorted(((p, k) for k, ps in INTENTS.items() for p in ps), key=lambda x: -len(_plain(x[0])))
    for phrase, kind in items:
        pp = f" {_plain(phrase)} "
        while pp in rest:
            found.add(kind)
            rest = rest.replace(pp, " ", 1)
    return found, re.sub(r"\s+", " ", rest).strip()


# ----------------------------------------------------------------------------- structured content
def _legacy_sections(p: dict, lang: str) -> dict:
    steps = list((p.get("steps") or {}).get(lang) or [])
    prev = list((p.get("prevention_steps") or {}).get(lang) or [])
    signs = [l for l in prev if str(l).lower().lstrip().startswith("sign")]
    return {"signs": signs, "symptoms": [], "treatment": steps, "medication": [], "dose": [],
            "prevention": [l for l in prev if l not in signs], "refer": [], "condition_type": ""}


def _lang_content(p: dict, lang: str) -> Optional[dict]:
    s = (p.get("sections") or {}).get(lang)
    if s:
        sec = {k: list(s.get(k) or []) for k in SEC_KEYS}
        sec["condition_type"] = s.get("condition_type") or p.get("condition_type") or ""
    else:
        sec = _legacy_sections(p, lang)
        sec["condition_type"] = p.get("condition_type") or ""
    sec["title"] = (p.get("title") or {}).get(lang) or ""
    return sec if any(sec[k] for k in SEC_KEYS) else None


def _any_title(p: dict) -> str:
    return next(iter((p.get("title") or {}).values()), "")


def _source_lang(p: dict) -> str:
    if p.get("source_lang"):
        return p["source_lang"]
    for key in ("sections", "steps", "title"):
        d = p.get(key) or {}
        if d:
            return next(iter(d.keys()))
    return "en"


def dose_verified(p: dict) -> bool:
    """A dose is shown to farmers only if the vet who published it attested it AND cited an official source."""
    return bool(p.get("dose_verified")) and bool(str(p.get("dose_source") or "").strip())


def _clean_keep(lines: List[str], verified: bool) -> Tuple[List[str], int]:
    out, n = [], 0
    for ln in lines:
        c = _clean_line(ln)
        if len(c) < 4 or _PLACEHOLDER.match(c):
            continue
        if not verified and _DOSE.search(c):
            n += 1
            continue
        out.append(c)
    return list(dict.fromkeys(out)), n


def render_view(p: dict, lang: str) -> dict:
    """The one place where published content becomes farmer-visible text (dose gating included)."""
    src = _source_lang(p)
    used, fell = lang, False
    c = _lang_content(p, lang)
    if c is None:
        for l in (src, "en"):
            c = _lang_content(p, l)
            if c:
                used, fell = l, l != lang
                break
        else:
            c = {**{k: [] for k in SEC_KEYS}, "condition_type": p.get("condition_type") or "", "title": ""}
            used, fell = src, lang != src
    status = "reviewed" if fell else ((p.get("translation_status") or {}).get(lang) or ("reviewed" if lang == src else "needs_review"))
    ver = dose_verified(p)
    hidden = 0
    v: Dict[str, Any] = {"title": c["title"] or _any_title(p), "type": (c.get("condition_type") or "").lower(),
                         "language": used, "fell_back": fell, "status": status, "dose_verified": ver,
                         "dose_source": str(p.get("dose_source") or "") if ver else ""}
    for k in ("signs", "symptoms", "treatment", "prevention", "refer"):
        v[k], n = _clean_keep(c[k], ver)
        hidden += n
    v["medication"], n = _clean_keep(c["medication"], ver)
    hidden += n
    for pr in p.get("products") or []:
        name = str(pr.get("name") or pr.get("product") or "") if isinstance(pr, dict) else str(pr)
        name = _clean_line(name)[:80]
        if name and (ver or not _DOSE.search(name)) and name not in v["medication"]:
            v["medication"].append(name)
    if ver:
        v["dose"], _ = _clean_keep(c["dose"], True)
    else:
        v["dose"] = []
        hidden += len([x for x in c["dose"] if str(x).strip()])
    v["dose_hidden"] = hidden
    v["has_content"] = any(v[k] for k in ("signs", "symptoms", "treatment", "medication", "dose", "prevention", "refer"))
    return v


# ----------------------------------------------------------------------------- index
class Index:
    def __init__(self, procs: List[dict], version: Any = 0, aliases: Optional[Dict[str, List[str]]] = None):
        self.version = version
        self.aliases = aliases or {}
        self.docs: List[dict] = []
        for p in procs:
            if p.get("status") == "published":
                self.docs.append(self._make(p, self.aliases.get(p.get("id"), [])))
        self.N = len(self.docs)
        df: Counter = Counter()
        for d in self.docs:
            df.update(d["tf"].keys())
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.avgdl = (sum(d["len"] for d in self.docs) / self.N) if self.N else 1.0

    @staticmethod
    def _make(p: dict, aliases: List[str]) -> dict:
        tf: Counter = Counter()
        for t in (p.get("title") or {}).values():
            for tok in tokens(t):
                tf[tok] += 3
        langs = set((p.get("sections") or {}).keys()) | set((p.get("steps") or {}).keys()) | set((p.get("prevention_steps") or {}).keys())
        weights = {"signs": 2, "symptoms": 2, "treatment": 1, "medication": 1, "prevention": 1, "refer": 1}
        for l in langs:
            c = _lang_content(p, l)
            if not c:
                continue
            for k, w in weights.items():
                for line in c[k]:
                    for tok in tokens(str(line)):
                        tf[tok] += w
        for f in _facts(p.get("full_text") or ""):
            for tok in tokens(f):
                tf[tok] += 1
        for a in aliases:                       # expert-approved farmer/local words for THIS condition
            for tok in tokens(a):
                tf[tok] += 2
        return {"id": p.get("id"), "host": (p.get("host_key") or "").lower(), "p": p, "tf": tf,
                "len": max(1, sum(tf.values())), "dangerous": _is_dangerous(p)}

    def doc_tokens(self, pid: str) -> set:
        for d in self.docs:
            if d["id"] == pid:
                return set(d["tf"].keys())
        return set()

    def weight(self, t: str) -> float:
        return max(self.idf.get(t, 1.0), 0.3)

    def search(self, q: List[str], host: str) -> List[Tuple[float, float, dict]]:
        q = list(dict.fromkeys(q))
        total = sum(self.weight(t) for t in q) or 1.0
        k1, b = 1.4, 0.75
        res = []
        for d in self.docs:
            if host and d["host"] != host:
                continue
            score = matched = 0.0
            for t in q:
                f = d["tf"].get(t, 0)
                if f:
                    w = self.weight(t)
                    score += w * f * (k1 + 1) / (f + k1 * (1 - b + b * d["len"] / self.avgdl))
                    matched += w
            res.append((score, matched / total, d))
        res.sort(key=lambda x: (-x[0], str(x[2]["id"])))
        return res


_CACHE: Dict[str, Any] = {"v": None, "idx": None}


def get_index(procs: List[dict], version: Any, aliases: Optional[Dict[str, List[str]]] = None) -> Index:
    key = (version, tuple(sorted((k, tuple(v)) for k, v in (aliases or {}).items())))
    if _CACHE["idx"] is None or _CACHE["v"] != key:
        _CACHE["idx"], _CACHE["v"] = Index(procs, version, aliases), key
    return _CACHE["idx"]


# ----------------------------------------------------------------------------- answers
def _result(lang: str, outcome: str, reply: str, **kw: Any) -> dict:
    L = UI[lang]
    band = kw.pop("band", "low")
    r = {
        "reply": reply, "language": lang, "outcome": outcome,
        "confidence": {"band": band, "coverage": kw.pop("coverage", 0.0), "label": L.get("conf_" + band, "")},
        "emergency": outcome == "emergency", "referral_required": outcome in ("emergency", "not_sure"),
        "sources": [], "images": [], "quick_replies": [], "notices": [], "passages": [], "sections": {},
        "procedure_ids": [], "needs_translation": False, "llm_context": "", "host_key": kw.pop("host_key", ""),
        "query_tokens": [], "memory": None,
        "source": {"answer": "published_procedure", "catalog": "published_catalog"}.get(outcome, outcome),
        "ui_review_status": UI_REVIEW_STATUS,
        "safety": {"invent_treatments": False, "grounded_on_published_only": True, "emergency_rules_fixed": True,
                   "doses_shown_only_if_vet_verified_with_source": True},
    }
    r.update(kw)
    return r


def emergency(lang: str, critical_steps: Callable[[str], List[str]], name: str = "", reason: str = "") -> dict:
    L = UI[lang]
    steps = critical_steps(lang)
    title = L["emergency_title"] + (f" ({name})" if name else "")
    reply = title + "\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)) + "\n" + L["emergency_expert"]
    return _result(lang, "emergency", reply, band="high", coverage=1.0, reason=reason)


def detect_danger(message: str, host: str) -> Optional[str]:
    plain = _plain(message)
    if host and host not in LIVESTOCK:
        return None
    for t in DANGER_TERMS:
        if _has_phrase(plain, t):
            return t
    if host in LIVESTOCK:
        for s in DANGER_SIGNS:
            if _has_phrase(plain, s):
                return s
    return None


def query_tokens(message: str, description: str = "", host: str = "", host_label: str = "") -> List[str]:
    host_toks = set(tokens(host)) | set(tokens(host_label))
    q = [t for t in tokens(clean_user_text(message)) if t not in host_toks]
    if len(q) < 2:
        q += [t for t in tokens(clean_user_text(description, 1200)) if t not in host_toks]
    return list(dict.fromkeys(q))


def _title_for(p: dict, lang: str) -> str:
    return (p.get("title") or {}).get(lang) or (p.get("title") or {}).get(_source_lang(p)) or _any_title(p)


def _catalog(idx: Index, lang: str, host: str, label: str) -> dict:
    L = UI[lang]
    seen, titles, ids = set(), [], []
    for d in idx.docs:
        if host and d["host"] != host:
            continue
        t = _title_for(d["p"], lang)
        key = _plain(t)
        if not key or key in seen or d["dangerous"]:
            continue
        seen.add(key)
        typ = (_lang_content(d["p"], _source_lang(d["p"])) or {}).get("condition_type") or ""
        titles.append(t + (f" ({L.get('t_' + typ, typ)})" if typ else ""))
        ids.append(d["id"])
    if not titles:
        return _result(lang, "not_sure", L["none_for_host"].replace("{h}", label or host or "?"), host_key=host)
    reply = L["list_title"].replace("{h}", label or host) + ":\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(titles[:20], 1))
    reply += "\n" + L["ask_expert"]
    return _result(lang, "catalog", reply, band="high", coverage=1.0, quick_replies=[re.sub(r" \(.*\)$", "", t) for t in titles[:6]],
                   procedure_ids=ids[:20], host_key=host)


def _rank_lines(lines: List[str], qset: set, limit: int) -> List[str]:
    if not qset or len(lines) <= limit:
        return lines[:limit]
    scored = [(len(qset & set(tokens(l))), i, l) for i, l in enumerate(lines)]
    top = sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]
    top.sort(key=lambda x: x[1])
    return [l for _, _, l in top]


def _date(p: dict) -> str:
    return str(p.get("approved_at") or p.get("updated_at") or "")[:10]


def _assemble(parts: dict, note: str = "") -> str:
    out = [parts["head"]] + parts.get("notices", []) + [parts["body"]]
    if note:
        out.append(note)
    out += [parts["foot"], parts["source"]]
    return "\n".join(x for x in out if x)


def answer(idx: Index, message: str, lang: str = "en", host_key: str = "", description: str = "",
           critical_steps: Optional[Callable[[str], List[str]]] = None,
           normalize_host: Optional[Callable[[str], str]] = None, host_label: str = "",
           prior: Optional[Dict[str, float]] = None) -> dict:
    """prior: {procedure_id: 0..1} from expert-confirmed cases. It only re-orders candidates that ALREADY
    pass the coverage threshold; it can never rescue a weak match or override an emergency."""
    lang = lang if lang in UI else "en"
    L = UI[lang]
    critical_steps = critical_steps or (lambda l: [])
    norm = normalize_host or (lambda h: (h or "").lower().strip())
    msg, desc = clean_user_text(message), clean_user_text(description, 1200)
    host = norm(host_key)
    prior = prior or {}

    hit = detect_danger(f"{msg} {desc}", host)
    if hit:
        return emergency(lang, critical_steps, reason=hit)

    plain = _plain(msg)
    found, rest = split_intents(plain)
    greeted = "greeting" in found
    if found:
        if not tokens(rest):                                   # pure small talk: fixed, localized text
            for kind in ("about", "greeting", "thanks", "bye", "okay"):
                if kind in found:
                    return _result(lang, "smalltalk", L[_INTENT_KEY[kind]], band="none", host_key=host)
        msg, plain = rest, _plain(rest)                        # "Hello, my maize has spots" -> answer the question
    dose_asked = any(f" {_plain(w)} " in f" {plain} " for w in _DOSE_Q)
    if host and any(_has_phrase(plain, w) for w in _LIST_WORDS):
        return _catalog(idx, lang, host, host_label)

    q = query_tokens(msg, desc, host, host_label)
    if not q:
        return _result(lang, "prompt", L["empty_query"], host_key=host)
    if host and not any(d["host"] == host for d in idx.docs):
        return _result(lang, "not_sure", L["none_for_host"].replace("{h}", host_label or host), host_key=host, query_tokens=q)

    cands, seen = [], set()
    for score, cov, d in idx.search(q, host):
        t = _title_for(d["p"], lang)
        key = _plain(t or str(d["id"]))
        if key in seen or score <= 0:
            continue
        seen.add(key)
        cands.append((score, cov, d, t))
    if not cands or cands[0][1] < MIN_COVERAGE:
        near = [t for s, c, d, t in cands[:3] if c >= MIN_COVERAGE * 0.5 and not d["dangerous"] and t]
        return _result(lang, "not_sure", L["not_sure"] + "\n" + L["ask_expert"], band="low",
                       coverage=round(cands[0][1], 3) if cands else 0.0, quick_replies=near, host_key=host, query_tokens=q)
    ok = [(s * (1 + 0.3 * prior.get(d["id"], 0.0)), s, c, d, t) for s, c, d, t in cands if c >= MIN_COVERAGE]
    ok.sort(key=lambda x: -x[0])
    adj1, _, c1, top, title = ok[0]
    close = [r for r in ok[:3] if r[0] >= AMBIGUITY_RATIO * adj1]
    if len(close) > 1:
        titles = [r[4] for r in close if r[4]]
        reply = L["did_you_mean"] + "\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1))
        return _result(lang, "clarify", reply, band="medium", coverage=round(c1, 3), quick_replies=titles,
                       host_key=host, procedure_ids=[r[3]["id"] for r in close], query_tokens=q)
    if top["dangerous"]:
        r = emergency(lang, critical_steps, name=title, reason="published_entry_flagged")
        r["query_tokens"], r["procedure_ids"] = q, [top["id"]]
        return r

    p = top["p"]
    v = render_view(p, lang)
    if not v["has_content"]:
        return _result(lang, "not_sure", L["not_sure"] + "\n" + L["ask_expert"], host_key=host, query_tokens=q)
    qset = set(q)
    signs, symptoms = _rank_lines(v["signs"], qset, 4), _rank_lines(v["symptoms"], qset, 4)
    treat, meds, dose = v["treatment"][:6], v["medication"][:6], v["dose"][:6]
    prev, refer = v["prevention"][:4], v["refer"][:3]
    title = v["title"] or title

    body: List[str] = []
    if v["type"]:
        body.append(f"{L['type_label']}: {L.get('t_' + v['type'], v['type'])}")
    for label, lines, numbered in ((L["signs"], signs, False), (L["symptoms"], symptoms, False),
                                   (L["steps"], treat, True), (L["medicines"], meds, False),
                                   (L["dose_label"], dose, False), (L["prevention"], prev, False),
                                   (L["refer"], refer, False)):
        if lines:
            body.append(label + ":")
            if numbered:
                body += [f"{i}. {s}" for i, s in enumerate(lines, 1)]
            else:
                body += [f"\u2022 {s}" for s in lines]
    notices = []
    if v["fell_back"]:
        notices.append(L["lang_fallback"])
    elif v["status"] != "reviewed":
        notices.append(L["translation_unreviewed"])
    foot = []
    if dose:
        foot.append(f"{L['dose_source']}: {v['dose_source']}")
        foot.append(L["follow_label"])
    elif dose_asked or v["dose_hidden"] > 0:
        foot.append(L["dose_ask"])
    if meds or dose or _CHEM.search(" ".join(treat + prev + meds)):
        foot.append(L["chem_note"])
    foot.append(L["ask_expert"])
    src_bits = [str(p.get("source_filename") or title)]
    if _date(p):
        src_bits.append(f"{L['approved']}: {_date(p)}")
    src_line = L["source"] + ": " + " \u00b7 ".join(src_bits)
    if p.get("approved_by"):
        src_line += f" ({p['approved_by']})"
    head = (L["hello_short"] + "\n" if greeted else "") + f"{L['from_library']}: {title}"
    parts = {"head": head, "notices": notices, "body": "\n".join(body), "foot": "\n".join(foot), "source": src_line}
    band = "high" if c1 >= HIGH_COVERAGE else "medium"
    return _result(
        lang, "answer", _assemble(parts), band=band, coverage=round(c1, 3), host_key=host or top["host"],
        notices=notices, procedure_ids=[top["id"]], sources=[src_line], query_tokens=q,
        needs_translation=v["fell_back"], llm_context="\n".join([head, parts["body"]]), text_parts=parts,
        sections={"type": v["type"], "signs": signs, "symptoms": symptoms, "treatment": treat, "medication": meds,
                  "dose": dose, "prevention": prev, "refer": refer, "dose_source": v["dose_source"]},
        passages=[{"name": title, "host_key": top["host"], "procedure_id": top["id"], "steps": treat,
                   "prevention": prev, "products": meds, "excerpts": []}],
        has_medicine=bool(meds or dose),
    )


def with_memory_note(ans: dict, lang: str, farmers: int, days: int, case_count: int = 0) -> dict:
    """Add 'N other farmers near you asked...' only when at least K_MIN_FARMERS distinct devices (privacy)."""
    if ans.get("outcome") != "answer" or farmers < K_MIN_FARMERS:
        return ans
    note = UI[lang]["similar_seen"].replace("{n}", str(farmers)).replace("{d}", str(days))
    ans["memory"] = {"farmers": farmers, "days": days, "cases": case_count, "note": note}
    parts = ans.get("text_parts")
    if parts:
        ans["reply"] = _assemble(parts, note)
        parts["note"] = note
    return ans


# ----------------------------------------------------------------------------- LLM (optional)
def verify_llm_output(output: str, context: str) -> bool:
    if not output or len(output) > 3000 or re.search(r"https?://|www\.", output, re.I):
        return False
    nums = lambda s: set(re.findall(r"\d+(?:[.,]\d+)?", s))
    if not nums(output) <= nums(context):
        return False
    return not (_DOSE.search(output) and not _DOSE.search(context))


def finalize_translation(ans: dict, translated: str, lang: str) -> dict:
    L = UI[lang]
    parts = dict(ans.get("text_parts") or {})
    if not parts:
        return ans
    parts.update(head="", notices=[L["machine_translated"]], body=translated.strip())
    ans["reply"] = _assemble(parts, parts.get("note", ""))
    ans["notices"] = [L["machine_translated"]]
    ans["machine_translated"] = True
    return ans


# ----------------------------------------------------------------------------- offline pack
def build_pack(procs: List[dict], critical: Dict[str, List[str]], version: Any,
               aliases: Optional[Dict[str, List[str]]] = None, nearby: Optional[Dict[str, int]] = None) -> dict:
    docs = []
    for p in procs:
        if p.get("status") != "published":
            continue
        views = {}
        for l in LANGS:
            v = render_view(p, l)
            if v["has_content"]:
                views[l] = {k: v[k] for k in ("title", "type", "signs", "symptoms", "treatment", "medication", "dose",
                                              "prevention", "refer", "status", "fell_back", "dose_source", "dose_hidden")}
        docs.append({"id": p.get("id"), "host_key": p.get("host_key"), "views": views,
                     "source_filename": p.get("source_filename") or "", "approved_at": _date(p),
                     "approved_by": p.get("approved_by") or "", "dangerous": _is_dangerous(p),
                     "aliases": (aliases or {}).get(p.get("id"), []),
                     "facts": [f[:200] for f in _facts(p.get("full_text") or "")[:25]]})
    return {"version": version, "lexicon": LEXICON, "stop": sorted(_STOP), "danger_terms": DANGER_TERMS,
            "danger_signs": DANGER_SIGNS, "intents": INTENTS, "ui": UI, "critical": critical, "procedures": docs,
            "nearby": {k: v for k, v in (nearby or {}).items() if v >= K_MIN_FARMERS},
            "min_coverage": MIN_COVERAGE, "high_coverage": HIGH_COVERAGE, "ui_review_status": UI_REVIEW_STATUS}
