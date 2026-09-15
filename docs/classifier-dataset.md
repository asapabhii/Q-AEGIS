# FR-1 classifier dataset contract

`SPEC.md` 3.2 and `PRD.md` Section 9 block the real classifier on a labelled
dataset. Do not train the production classifier on synthetic labels or on the
keyword stub's own outputs; that would only distill the stub and make it harder
to detect.

## Required file

Training expects a CSV file with these columns:

| Column | Required | Notes |
|---|---:|---|
| `content` | yes | Extracted document text. Blank rows are rejected. |
| `label` | yes | One of `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`. |
| `source_id` | no | Original dataset/document identifier for traceability. |
| `split` | no | Optional `train`, `validation`, or `test`. If omitted, the trainer creates a stratified holdout split. |

## Acceptance bar

- Keep a held-out test split that is not used for training or threshold tuning.
- Report macro F1, per-label precision/recall/F1, accuracy, and calibration
  error.
- Record the model version and dataset fingerprint in the evaluation artifact.
- Preserve the classifier fail-safe: low-confidence predictions must still
  escalate toward more protection.

## Current status

No labelled dataset is committed to this repository. The keyword classifier in
`backend/app/classifier/stub_classifier.py` remains a STUB until a trained model
artifact and evaluation report are produced from real labelled data.
