# Photo detection: which crop or animal is this?

**Status: demo, NOT validated.** The app *suggests* the crop/animal from the photo; the farmer always confirms
("This looks like Maize. Is that right?") before any advice. No photo is stored: only the fingerprint used by the
case memory, and an agree/disagree counter (`/v1/scan/identify/feedback`, shown in the portal status as `photo_detector`).

## Turn it on (server)
Pick ONE backend with `MASOMLIMI_DETECTOR`:

| value | what it does | install |
|---|---|---|
| `clip` | zero-shot CLIP: works immediately, no training data | `pip install transformers torch` (downloads ~600 MB of weights on first use; needs internet that one time) |
| `onnx` | your own classifier | `pip install onnxruntime numpy`; put `backend/app/models/host_classifier.onnx` and `host_labels.json` (list of host keys in output order); input 1x3x224x224, ImageNet-normalised |
| *(unset)* | no detection: the farmer picks from a list (hosts with published advice first). This is also what happens offline | none |

If the model is missing, crashes, or is unsure, the app simply shows the list. Nothing breaks.

## Safety behaviour (tested in tests/test_detector.py)
- Suggested only when the top guess >= 0.70 AND it beats the runner-up by >= 0.20 (`MASOMLIMI_DETECT_MIN_TOP`, `MASOMLIMI_DETECT_MIN_MARGIN`).
- Close call or low confidence: no suggestion, farmer chooses.
- A goat photo under "Crops" (or a plant under "Livestock"): the app asks to switch category instead of guessing.
- Only crops/animals of the chosen category are offered.

## Before this can be called "production" (launch gate)
1. Collect local labelled photos (maize, cassava, tomato, beans, groundnuts, rice, tobacco, chickens, goats, cattle, pigs...) from different farms/districts.
2. Measure accuracy on a held-out set. Target: >= 90% precision at the confident threshold; everything else goes to "choose".
3. Train/fine-tune your own classifier (export to ONNX / TFLite for the phone so it also works offline) and re-tune the thresholds.
4. Watch `photo_detector.agreement_rate` and the confusion pairs in the portal status while piloting.
Identifying the *crop* is much easier than identifying the *disease*. Disease diagnosis from the photo is a separate, later gate.
