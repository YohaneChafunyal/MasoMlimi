# Certified photo ML — launch gate (not optional for "main solution" claim)

MasoMlimi safety rules:

1. AI may assist recognition only.
2. All treatment/guidance text must come from expert-published library.
3. Below confidence threshold → "not sure, ask expert".
4. Dangerous/reportable animal diseases → safety actions + refer only.

## To activate real photo diagnosis

1. Collect local field photos (district crops/livestock) with consent.
2. Expert labelling of conditions.
3. Train model (e.g. TFLite) and evaluate on held-out local set.
4. Independent review of false positives on dangerous diseases.
5. Place `backend/app/models/crop_livestock.tflite` and wire inference in `scan_analyze`.
6. Document metrics in evaluation report.

Until then `/v1/scan/analyze` accepts the photo, applies safety rules, and returns **published** guidance for that host or referral — it does **not** invent a disease name from pixels.
