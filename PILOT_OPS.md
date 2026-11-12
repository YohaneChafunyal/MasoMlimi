# MasoMlimi pilot ops (what code does vs external)

## Implemented in code
- API security headers (nosniff, frame deny)
- Optional MASOMLIMI_API_KEY on publish/delete
- /v1/metrics monitoring snapshot
- /v1/translate glossary + optional LIBRETRANSLATE_URL
- Scan chat interview → record_scan (dashboard totals)
- Farmer contributions → auto DRAFT procedures (never auto-publish medicines)
- OCR hooks (pytesseract/pdf2image if installed on server)
- Chat poll ~3s; WebSocket broadcast when connected
- Pack sync replaces deleted guides

## Requires external setup (not inventable in app alone)
- HTTPS: reverse proxy (Caddy/nginx) + Let's Encrypt certificates
- Full NMT: set LIBRETRANSLATE_URL or commercial MT API
- Push (FCM/APNs): Firebase project + google-services.json
- Certified photo ML: labelled local photos + train TFLite + safety eval → place models/crop_livestock.tflite
- Pen-test: independent security firm
- Auto-publish treatments from every chat: **disabled by design** — auto-draft only; officer Publish required

## Why auto-publish treatments is not enabled
Inventing or auto-releasing medicines from unverified farmer chat violates safety rules and can harm people and animals. Field notes become drafts for qualified officers.
