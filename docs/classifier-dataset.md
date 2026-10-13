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
| `label` | yes | One of `PUBLIC`, `CONFIDENTIAL`, `RESTRICTED`. `INTERNAL` is a policy-layer tier and is **rejected** from training data (see below). |
| `source_id` | no | Original dataset/document identifier for traceability. |
| `split` | no | Optional `train`, `validation`, or `test`. If omitted, the trainer creates a stratified holdout split. |

## Three model tiers, not four

The trained model predicts only the markings a public corpus actually carries:
`PUBLIC`, `CONFIDENTIAL`, `RESTRICTED`. `INTERNAL` is assigned downstream by the
policy layer, never by the ML model — no public dataset carries an "internal"
marking, and synthesising one would train the model on an invented label.
`app/classifier/training.py` rejects any `INTERNAL` row, and the runtime keeps
the keyword rules as an escalation-only override so a hard identifier the model
misses is still caught.

## Chosen datasets

- **Primary (labels): FOIArchive** (`HistoryLab/foiarchive`, CC-BY-NC-4.0,
  gated). Real government classification markings are the label ground truth.
  Gated: Abhinav must log into HuggingFace and accept the dataset's terms on its
  page before it can be downloaded. Because the licence is non-commercial and
  share-restricted, the **trained artifact ships, not the corpus** — the CSV and
  raw documents stay out of the repository.
- **Interim (labels): WikiLeaks diplomatic cables** (`fn5/wikileaks-cables`,
  US Government works, public domain). Non-gated, so training is not blocked
  while FOIArchive access is pending. The cables carry the same marking
  vocabulary (`UNCLASSIFIED`/`CONFIDENTIAL`/`SECRET`/`TOP SECRET`), so the same
  `map_marking` and `convert` core is reused. **This is a development stand-in:
  the shipped model is retrained on FOIArchive once access is granted, and the
  interim artifact is swapped out.** The corpus is not committed either.
- **Held-out eval: TAB** (`mattmdjaga/text-anonymization-benchmark-train`, MIT,
  ~1268 expert-annotated ECHR documents). A clean, differently-sourced set for
  reporting generalisation, kept separate from the training corpus.

Marking → tier mapping (`app/classifier/prep_foiarchive.py`): `unclassified` →
`PUBLIC`; `confidential` → `CONFIDENTIAL`; `secret` and `top secret` →
`RESTRICTED`. Handling caveats after a `/` are ignored; any other marking (e.g.
"limited official use") is **skipped, not guessed**, and its count is reported.

## No label leakage from the document body

A diplomatic cable prints its own classification inside the text — the body is
headed `S E C R E T` or `C O N F I D E N T I A L` (spelled out, letter-spaced).
Left in, a model would learn to *read the marking off the page* rather than learn
genuine sensitivity features, and held-out accuracy would be a meaningless
string-match. `app/classifier/prep_wikileaks_cables.py::strip_cable_markings`
removes the marking tokens, their handling caveats (`NOFORN`, `SIPDIS`, …), and
`SECTION nn OF nn` pagination, while deliberately preserving legitimate prose
(`Secretary`, `SECSTATE`). Standalone-marking survival into the training text is
asserted to ~0 before any artifact is trained.

## Out-of-core streaming trainer for large corpora

The in-memory `train_from_csv` (TF-IDF + calibrated `LinearSVC`) fits the whole
vocabulary at once and cannot scale past available RAM — the full cables corpus
(124,745 rows) OOMs on a 3.5 GB-free host. `train_from_csv_streaming`
(`--streaming`) trains the identical representation out-of-core:

- `HashingVectorizer` (stateless, no stored vocabulary) emits raw hashed counts;
- per-feature document frequencies are accumulated in one bounded streaming pass
  and the exact scikit-learn smooth-IDF is reconstructed and injected into a
  `TfidfTransformer`, so the TF-IDF representation the minority (RESTRICTED)
  class depends on is preserved without ever materialising the corpus matrix;
- an `SGDClassifier(loss="hinge")` — the same linear-SVM objective as the
  in-memory `LinearSVC` — is trained by minibatch `partial_fit` over several
  epochs, with balanced class weights computed up front from train-fold counts;
- probabilities are recovered by a prefit sigmoid `CalibratedClassifierCV` on a
  held-out calibration fold; a separate held-out test fold produces the report.

Peak memory is bounded by `batch_size`, not corpus size. The train/calibration/
test split is a deterministic hash of each row key, the out-of-core analogue of a
seeded `train_test_split`.

## Producing the dataset and model

### Interim path (WikiLeaks cables, in use now)

```
# 1. Convert the cables to the CSV, scrubbing in-body markings (no label leakage).
python -m app.classifier.prep_wikileaks_cables --hf-dataset fn5/wikileaks-cables \
    --hf-data-files cables_parsed.jsonl --output data/wikileaks_cables.csv

# 2. Train out-of-core over the full corpus (124,745 rows) — bounded memory.
python -m app.classifier.training data/wikileaks_cables.csv \
    --version wikileaks-cables-hashing-svm-1.0.0 --streaming --epochs 8

# 3. Activate: point the runtime at the artifact.
#    CLASSIFIER_MODEL_PATH=artifacts/classifier/wikileaks-cables-hashing-svm-1.0.0.joblib
```

### Primary path (FOIArchive, once access is granted)

```
# 1. Convert a FOIArchive export (JSONL, or stream from HuggingFace) to the CSV.
python -m app.classifier.prep_foiarchive --input foiarchive.jsonl --output data/classifier.csv
#    or: --hf-dataset HistoryLab/foiarchive --hf-config documents --output data/classifier.csv

# 2. Train (add --streaming for the full corpus).
python -m app.classifier.training data/classifier.csv --version foiarchive-hashing-svm-1.0.0 --streaming

# 3. Activate: point the runtime at the artifact and retire the interim one.
#    CLASSIFIER_MODEL_PATH=artifacts/classifier/foiarchive-hashing-svm-1.0.0.joblib
```

The `.joblib` is a metadata bundle (`model`, `model_version`, `labels`,
`dataset_fingerprint`), so every stored classification is attributable to the
artifact that produced it.

## Acceptance bar

- Keep a held-out test split that is not used for training or threshold tuning.
- Report macro F1, per-label precision/recall/F1, accuracy, and calibration
  error.
- Record the model version and dataset fingerprint in the evaluation artifact.
- Preserve the classifier fail-safe: low-confidence predictions must still
  escalate toward more protection.

## Current status

An **interim** classifier is trained and ships as
`artifacts/classifier/multigenre-hashing-svm-1.0.0.joblib`, produced by the
out-of-core streaming trainer (`HashingVectorizer` → injected-IDF
`TfidfTransformer` → calibrated `SGDClassifier`, hinge loss) over a broad, public
multi-genre corpus (train 33,139 / test 4,049). Broadening past the earlier
single-domain diplomatic-cables corpus is deliberate: the cables-only model
generalised poorly to arbitrary documents, biasing unseen genres toward PUBLIC.
Held-out results:

| Tier | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| PUBLIC | 0.938 | 0.959 | 0.948 | 1515 |
| CONFIDENTIAL | 0.877 | 0.837 | 0.857 | 1487 |
| RESTRICTED | 0.822 | 0.848 | 0.835 | 1047 |

Accuracy 0.886, macro F1 0.880. RESTRICTED is the safety-critical minority tier;
its recall (0.848, up from 0.604 on the cables-only model) is the headline gain
from the broader corpus, and the runtime low-confidence fail-safe (escalate
toward more protection) plus the high-precision content detectors
(`backend/app/classifier/detectors.py`, escalation-only) cover the residual.

The earlier `wikileaks-cables-hashing-svm-1.0.0.joblib` is **superseded** and
retained only for provenance; the training recipe below documents how it was
produced. No labelled corpus is committed to this repository (neither the
public-domain source text nor, later, FOIArchive-derived text). Set
`CLASSIFIER_MODEL_PATH` to the multigenre artifact above to activate the trained
engine; otherwise the keyword engine in
`backend/app/classifier/stub_classifier.py` remains the labelled fallback. Once
Abhinav accepts the FOIArchive terms, the model is retrained on that corpus and
this interim artifact is retired.
