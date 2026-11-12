#!/usr/bin/env python3
"""Re-read the expert files already in backend/data/library_files and create ONE DRAFT PER CONDITION.

Why: files uploaded with the old version were stored as one flat draft per document, with only ~4,000
characters of text kept. This re-extracts the FULL text from the stored file and splits it by condition
with the new structured parser (type / signs / symptoms / treatment / medication / dose / prevention / refer).

Safe by default:
  * DRY RUN unless you pass --apply: shows what it would create, creates nothing.
  * Only creates DRAFTS (farmers never see them until a vet reviews and publishes).
  * Never deletes or edits existing procedures. Re-running does not duplicate (same host+title+file is skipped).

STOP the API server first (the JSON store would otherwise overwrite the changes), run, then restart it.

  python tools/reprocess_library.py                      # dry run, all library files
  python tools/reprocess_library.py --only Guide         # only files whose name contains "Guide"
  python tools/reprocess_library.py --apply --lang en
  python tools/reprocess_library.py --dump               # write the extracted text of each file to tools/dumps/*.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import doc_text, security, store, structure  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="create the drafts (default: dry run)")
    ap.add_argument("--lang", default="en", choices=["en", "ny", "fr", "sw", "pt"], help="language the files are written in")
    ap.add_argument("--only", default="", help="only library files whose name contains this text")
    ap.add_argument("--dump", action="store_true", help="write the extracted text to tools/dumps/ and stop (to inspect the layout)")
    a = ap.parse_args()

    items = [it for it in store.list_library(None) if it.get("stored_name")]
    items = [it for it in items if (a.only.lower() in (it.get("filename") or "").lower())]
    docs = [it for it in items if not (it.get("content_type") or "").startswith("image/")]
    if not docs:
        print("No document files found in the library.")
        return 0
    existing = {(p.get("host_key"), (next(iter((p.get("title") or {}).values()), "") or "").lower(), p.get("source_filename"))
                for p in store.list_procedures(True)}
    total_new = 0
    for it in docs:
        path = store.LIBRARY_DIR / it["stored_name"]
        if not path.is_file():
            print(f"[skip] {it.get('filename')}: file missing on disk")
            continue
        raw = path.read_bytes()
        kind = security.sniff_document(raw, it.get("filename") or "")
        if kind not in ("pdf", "docx", "txt"):
            print(f"[skip] {it.get('filename')}: not a text document")
            continue
        text = doc_text.extract_text(it.get("filename") or "", it.get("content_type") or "", raw, kind)
        print(f"\n=== {it.get('filename')}  ({len(text):,} characters read, host default: {it.get('host_key')})")
        if a.dump:
            out = ROOT / "tools" / "dumps"
            out.mkdir(exist_ok=True)
            f = out / (Path(it["stored_name"]).stem[:40] + ".txt")
            f.write_text(text, encoding="utf-8")
            print(f"   text written to {f}  ({len(text.splitlines())} lines)")
            continue
        if len(text.strip()) < 80:
            print("   almost no text: probably a scanned PDF. Install pytesseract + pdf2image for OCR, or upload a text version.")
            continue
        drafts = structure.drafts_from_text(text, it.get("host_key") or "maize", a.lang, it.get("filename") or "file",
                                            split_hosts=doc_text.split_document_by_hosts)
        if not drafts:
            print("   no conditions with labelled sections found (needs headings like 'Signs:', 'Treatment:').")
            continue
        if len(drafts) > 60:
            print(f"   NOTE: {len(drafts)} conditions found: check the titles below look like real condition names.")
        for d in drafts:
            title = next(iter(d["title"].values()))
            sec = d["sections"][a.lang]
            filled = ", ".join(f"{k} {len(sec[k])}" for k in structure.SEC_KEYS if sec.get(k)) or "nothing"
            key = (d["host_key"], title.lower(), d["source_filename"])
            dup = key in existing
            flag = "  (crop/animal UNSURE: vet must set it)" if d.get("needs_host_review") else ""
            print(f"   {'(exists) ' if dup else ''}[{d['host_key']}] {title}  ->  {filled}{flag}")
            if a.apply and not dup:
                proc = store.add_procedure(d)
                store.link_library_procedure(it["id"], proc["id"])
                existing.add(key)
                total_new += 1
    if a.apply:
        print(f"\nCreated {total_new} draft(s). Open the portal -> Procedures to review, fix the crop/animal (host), and publish.")
    else:
        print("\nDRY RUN: nothing was created. Check the list above; if it looks right, run again with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
