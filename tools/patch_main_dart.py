#!/usr/bin/env python3
"""Patch your existing mobile/lib/main.dart for the new MasoMlimi files.

Usage:  python tools/patch_main_dart.py mobile/lib/main.dart
  * writes a backup  main.dart.bak
  * removes the classes/functions that now live in their own files
        OfflineCache, ExpertChatPage(+State), KnowledgeChatPage(+State), LocalKb, translateTo
  * adds the imports, the chat-pack sync, the new UI strings
  * moves the 3 stray Portuguese strings inside the 'pt' map (they were outside it)
  * verifies the result and refuses to write if anything looks wrong
Dart-aware: skips strings (incl. ${...} interpolation), comments, raw and triple-quoted strings.
"""
from __future__ import annotations

import re
import shutil
import sys

REMOVE_CLASSES = ["OfflineCache", "ExpertChatPage", "_ExpertChatPageState", "KnowledgeChatPage", "_KnowledgeChatPageState", "LocalKb",
                  "CheckPage", "CameraScanPage", "_CameraScanPageState", "ScanReviewPage", "_ScanReviewPageState"]
REMOVE_FUNCS = ["translateTo"]
NEW_IMPORTS = ["import 'chat_engine.dart';", "import 'offline_cache.dart';", "import 'expert_chat_page.dart';", "import 'knowledge_chat_page.dart';",
               "import 'scan_flow.dart';"]

EXTRA_STRINGS = """    'reply': {'en': 'Reply', 'ny': 'Yankhani', 'fr': 'Répondre', 'sw': 'Jibu', 'pt': 'Responder'},
    'replyingTo': {'en': 'Replying to', 'ny': 'Mukuyankha', 'fr': 'Réponse à', 'sw': 'Unajibu', 'pt': 'A responder a'},
    'sourceLbl': {'en': 'Source', 'ny': 'Gwero', 'fr': 'Source', 'sw': 'Chanzo', 'pt': 'Fonte'},
    'lookingPhoto': {'en': 'Looking at your photo...', 'ny': "Tikuyang'ana chithunzi chanu...", 'fr': 'Analyse de la photo...', 'sw': 'Tunaangalia picha yako...', 'pt': 'A analisar a foto...'},
    'looksLike': {'en': 'This looks like', 'ny': 'Izi zikuoneka ngati', 'fr': 'Cela ressemble à', 'sw': 'Hii inaonekana kama', 'pt': 'Isto parece'},
    'yesRight': {'en': 'Yes, that is right', 'ny': 'Inde, ndi zolondola', 'fr': "Oui, c'est correct", 'sw': 'Ndiyo, ni sahihi', 'pt': 'Sim, está certo'},
    'chooseOther': {'en': 'No, choose another', 'ny': 'Ayi, sankhani china', 'fr': 'Non, choisir un autre', 'sw': 'Hapana, chagua kingine', 'pt': 'Não, escolher outro'},
    'whatIsThis': {'en': 'What is this?', 'ny': 'Ichi ndi chiyani?', 'fr': "Qu'est-ce que c'est ?", 'sw': 'Hii ni nini?', 'pt': 'O que é isto?'},
    'looksAnimal': {'en': 'This photo looks like an animal. Switch to Livestock?', 'ny': 'Chithunzi ichi chikuoneka ngati chiweto. Sinthani ku Ziweto?', 'fr': 'Cette photo ressemble à un animal. Passer à Animaux ?', 'sw': 'Picha hii inaonekana kama mnyama. Badilisha hadi Mifugo?', 'pt': 'Esta foto parece um animal. Mudar para Animais?'},
    'looksCrop': {'en': 'This photo looks like a plant. Switch to Crops?', 'ny': 'Chithunzi ichi chikuoneka ngati mbewu. Sinthani ku Mbewu?', 'fr': 'Cette photo ressemble à une plante. Passer à Cultures ?', 'sw': 'Picha hii inaonekana kama mmea. Badilisha hadi Mazao?', 'pt': 'Esta foto parece uma planta. Mudar para Culturas?'},
    'switchYes': {'en': 'Switch', 'ny': 'Sinthani', 'fr': 'Changer', 'sw': 'Badilisha', 'pt': 'Mudar'},
    'demoNote': {'en': 'Photo recognition is a demo and not validated. Please confirm what it is.', 'ny': 'Kuzindikira chithunzi ndi koyesera ndipo sikunatsimikizidwe. Chonde tsimikizani chomwe chiri.', 'fr': 'La reconnaissance de photo est une démo non validée. Veuillez confirmer.', 'sw': 'Utambuzi wa picha ni wa majaribio na haujathibitishwa. Tafadhali thibitisha ni nini.', 'pt': 'O reconhecimento de fotos é uma demonstração não validada. Confirme o que é.'},
"""

PT_FIX = [
    "    'rememberHost': 'Lembramos que isto é {h}. Pode atualizar o que vê, ou toque Obter conselho.',",
    "    'lastNotes': 'Notas anteriores: {n}',",
    "    'noPackTip': 'Um técnico deve Publicar um procedimento para {h}. Depois Quinta → Atualizar packs online.',",
]


class PatchError(Exception):
    pass


# ---------------------------------------------------------------- Dart-aware scanning
def skip_string(s: str, i: int) -> int:
    """s[i] is a quote (or r/R before it). Returns index after the closing quote."""
    raw = False
    if s[i] in "rR" and i + 1 < len(s) and s[i + 1] in "'\"":
        raw, i = True, i + 1
    q = s[i]
    triple = s.startswith(q * 3, i)
    i += 3 if triple else 1
    while i < len(s):
        c = s[i]
        if c == "\\" and not raw:
            i += 2
            continue
        if not raw and c == "$" and i + 1 < len(s) and s[i + 1] == "{":
            i = skip_code(s, i + 2)           # to the matching }
            continue
        if triple and s.startswith(q * 3, i):
            return i + 3
        if not triple and c == q:
            return i + 1
        if not triple and c == "\n":
            return i + 1                      # unterminated: stop at line end
        i += 1
    raise PatchError("unterminated string")


def skip_code(s: str, i: int) -> int:
    """Scan code from i (just after an opening brace) to just after its matching '}'."""
    depth = 1
    while i < len(s):
        c = s[i]
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = len(s) if j < 0 else j + 1
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2)
            if j < 0:
                raise PatchError("unterminated comment")
            i = j + 2
        elif c in "'\"" or (c in "rR" and i + 1 < len(s) and s[i + 1] in "'\"" and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] == "_"))):
            i = skip_string(s, i)
        elif c == "{":
            depth += 1
            i += 1
        elif c == "}":
            depth -= 1
            i += 1
            if depth == 0:
                return i
        else:
            i += 1
    raise PatchError("unbalanced braces")


def skip_parens(s: str, i: int) -> int:
    """s[i] == '(' ; returns index after matching ')'."""
    depth, i = 0, i
    while i < len(s):
        c = s[i]
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = len(s) if j < 0 else j + 1
            continue
        if c in "'\"" or (c in "rR" and i + 1 < len(s) and s[i + 1] in "'\"" and not (s[i - 1].isalnum() or s[i - 1] == "_")):
            i = skip_string(s, i)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise PatchError("unbalanced parentheses")


def remove_decl(s: str, name: str, kind: str) -> str:
    if kind == "class":
        m = re.search(rf"^(?:abstract\s+)?class\s+{re.escape(name)}\b", s, re.M)
    else:
        m = re.search(rf"^[A-Za-z_<>\[\],? ]+\s+{re.escape(name)}\s*\(", s, re.M)
    if not m:
        return s                                   # already removed: patcher is idempotent
    start = m.start()
    if kind == "class":
        brace = s.index("{", m.end())
    else:
        close = skip_parens(s, s.index("(", m.start()))
        rest = s[close:]
        if rest.lstrip().startswith("=>"):         # expression body: ends at ';' (not used here)
            raise PatchError(f"{name}: arrow function not supported")
        brace = close + rest.index("{")
    end = skip_code(s, brace + 1)
    # also remove directly preceding /// doc comments
    pre = s[:start]
    while True:
        mm = re.search(r"(?:^[ \t]*///[^\n]*\n)+\Z", pre, re.M)
        if not mm:
            break
        pre = pre[:mm.start()]
    return pre + s[end:].lstrip("\n")


def add_imports(s: str) -> str:
    last = None
    for m in re.finditer(r"^import\s+[^;]+;\s*$", s, re.M):
        last = m
    if not last:
        raise PatchError("no imports found")
    add = [i for i in NEW_IMPORTS if i not in s]
    if not add:
        return s
    return s[:last.end()] + "\n" + "\n".join(add) + s[last.end():]


def drop_unused_import(s: str, line_regex: str, symbols: list) -> str:
    m = re.search(line_regex, s, re.M)
    if not m:
        return s
    body = s[:m.start()] + s[m.end():]
    if any(re.search(rf"\b{sym}\b", body) for sym in symbols):
        return s
    return body


def fix_pt_strings(s: str) -> str:
    anchor = re.search(r"^[ \t]*'packLine':\s*'Guias: \{p\}[^\n]*\n", s, re.M)
    if not anchor:
        return s
    for ln in PT_FIX:
        key = ln.strip().split(":")[0]
        s = re.sub(rf"^[ \t]*{re.escape(key)}:\s*'(?:Lembramos|Notas anteriores|Um técnico)[^\n]*\n", "", s, flags=re.M)
    anchor = re.search(r"^[ \t]*'packLine':\s*'Guias: \{p\}[^\n]*\n", s, re.M)
    return s[:anchor.end()] + "\n".join(PT_FIX) + "\n" + s[anchor.end():]


def add_extra_strings(s: str) -> str:
    """Adds only the keys that are missing, so running the patcher again after an update is safe."""
    m = re.search(r"const extra = \{\n", s)
    if not m:
        raise PatchError("could not find 'const extra = {' in t()")
    missing = [ln for ln in EXTRA_STRINGS.splitlines(keepends=True)
               if ln.strip() and f"    {ln.strip().split(':')[0]}: {{'en'" not in s]
    return s[:m.end()] + "".join(missing) + s[m.end():]


def add_pack_sync(s: str) -> str:
    if "ChatEngine.syncPack" in s:
        return s
    pat = r"(await OfflineCache\.syncAll\(kApiBase\)\.catchError\(\(_\) => null\);)"
    if not re.search(pat, s):
        raise PatchError("could not find the syncAll call in _AppState._init")
    return re.sub(pat, r"\1\n    await ChatEngine.syncPack(kApiBase).catchError((_) => null);", s, count=1)


def patch(src: str) -> str:
    s = src
    for n in REMOVE_CLASSES:
        s = remove_decl(s, n, "class")
    for n in REMOVE_FUNCS:
        s = remove_decl(s, n, "func")
    s = add_imports(s)
    s = fix_pt_strings(s)
    s = add_extra_strings(s)
    s = add_pack_sync(s)
    s = drop_unused_import(s, r"^import 'package:record/record\.dart';\s*\n", ["AudioRecorder", "RecordConfig", "AudioEncoder"])
    s = drop_unused_import(s, r"^import 'package:audioplayers/audioplayers\.dart';\s*\n", ["AudioPlayer", "DeviceFileSource"])
    s = drop_unused_import(s, r"^import 'package:image_picker/image_picker\.dart';\s*\n", ["ImagePicker", "ImageSource"])
    # verification
    for n in REMOVE_CLASSES:
        if re.search(rf"^class\s+{n}\b", s, re.M):
            raise PatchError(f"{n} still present")
    for imp in NEW_IMPORTS:
        if imp not in s:
            raise PatchError(f"missing import {imp}")
    return s


def balanced(s: str) -> bool:
    depth, i = 0, 0
    while i < len(s):
        c = s[i]
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = len(s) if j < 0 else j + 1
        elif s.startswith("/*", i):
            i = s.find("*/", i + 2) + 2
        elif c in "'\"" or (c in "rR" and i + 1 < len(s) and s[i + 1] in "'\"" and not (s[i - 1].isalnum() or s[i - 1] == "_")):
            i = skip_string(s, i)
        else:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth < 0:
                    return False
            i += 1
    return depth == 0


def main(argv: list) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = argv[1]
    src = open(path, encoding="utf-8").read()
    try:
        out = patch(src)
        if not balanced(out):
            raise PatchError("result has unbalanced braces; nothing written")
    except PatchError as e:
        print(f"PATCH FAILED: {e}. {path} was NOT changed.")
        return 1
    shutil.copyfile(path, path + ".bak")
    open(path, "w", encoding="utf-8").write(out)
    print(f"OK. Backup: {path}.bak  ({len(src.splitlines())} -> {len(out.splitlines())} lines)")
    print("Next: flutter pub get && flutter analyze")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
