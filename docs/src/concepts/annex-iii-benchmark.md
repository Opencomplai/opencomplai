# Annex III detection benchmark

A measurement of how well the deterministic code-signal matcher points a program
at an EU AI Act Annex III area. It is a baseline for tuning the signals, not a
claim about accuracy on real repositories.

## What is measured

The matcher is run over a set of small labelled programs through the same
`run_scan` entry point the CLI uses, with the working directory set to the
program's own root as in a normal checkout. Each program has an expected Annex
III area (1 to 8) or no area at all. Two paths are measured because they answer
different questions:

- **Intent path** (`scan --ai-intent`): a project counts as predicted for an area
  when any call site yields a high-risk finding for that area. A call site that
  matches Annex III vocabulary but is downgraded because the scored subject is a
  product, portfolio or other entity counts as not predicted.
- **Default scan path** (`check --scan`): no intent analysis runs. A project counts
  as predicted for an area when `detected_categories` holds that area's key. This
  is the path on which the token dictionary acts directly.

For area `a`: a true positive (TP) is a program labelled `a` with `a` predicted; a
false positive (FP) is a program not labelled `a` with `a` predicted; a false
negative (FN) is a program labelled `a` without `a` predicted. Precision is
TP / (TP + FP) and recall is TP / (TP + FN); `n/a` means the denominator is 0.
The `Overall` row sums TP, FP and FN over the eight areas (micro-average).

## Results

46 programs: 29 labelled with an Annex III area (at least three per area) and 17
with no area, including look-alikes such as a photo filter built on `opencv`, a
speech-to-text notes app, an internal analytics dashboard and a loan calculator.

### Intent path

| Area | Name | Fixtures | TP | FP | FN | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | biometrics | 4 | 4 | 0 | 0 | 100.0% | 100.0% |
| 2 | critical_infrastructure | 3 | 1 | 0 | 2 | 100.0% | 33.3% |
| 3 | education | 4 | 4 | 0 | 0 | 100.0% | 100.0% |
| 4 | employment | 4 | 3 | 0 | 1 | 100.0% | 75.0% |
| 5 | essential_services | 5 | 5 | 8 | 0 | 38.5% | 100.0% |
| 6 | law_enforcement | 3 | 2 | 0 | 1 | 100.0% | 66.7% |
| 7 | migration | 3 | 1 | 0 | 2 | 100.0% | 33.3% |
| 8 | justice_democracy | 3 | 2 | 0 | 1 | 100.0% | 66.7% |
| Overall | all areas | 29 | 22 | 8 | 7 | 73.3% | 75.9% |

Programs with no Annex III area that stay clean (no area predicted): 16 of 17.

### Default scan path

| Area | Name | Fixtures | TP | FP | FN | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | biometrics | 4 | 4 | 5 | 0 | 44.4% | 100.0% |
| 2 | critical_infrastructure | 3 | 0 | 0 | 3 | n/a | 0.0% |
| 3 | education | 4 | 0 | 0 | 4 | n/a | 0.0% |
| 4 | employment | 4 | 0 | 0 | 4 | n/a | 0.0% |
| 5 | essential_services | 5 | 0 | 0 | 5 | n/a | 0.0% |
| 6 | law_enforcement | 3 | 0 | 0 | 3 | n/a | 0.0% |
| 7 | migration | 3 | 0 | 0 | 3 | n/a | 0.0% |
| 8 | justice_democracy | 3 | 0 | 0 | 3 | n/a | 0.0% |
| Overall | all areas | 29 | 4 | 5 | 25 | 44.4% | 13.8% |

Programs with no Annex III area that stay clean (no area predicted): 14 of 17.

No program triggered an Article 5 prohibited-practice finding on the intent path.

## How to read this

- **The fixtures are synthetic and author-labelled.** They are short programs
  written for this benchmark, labelled by one author from the Annex III text as
  encoded in the knowledge pack. Nobody else has reviewed the labels. A
  program's declared purpose is passed to the scan as the declared purpose only;
  it is not written into the program's files, so the matcher reads nothing but
  each program's own code and requirements.
- **The numbers are not accuracy on real repositories.** Real projects are larger
  and use different names. The table fixes a baseline so a change to the signals
  can be seen as a change in these counts, and the false positives of the
  look-alike programs show which vocabulary over-fires.
- **A person confirms any proposed classification.** Classification from code is
  proposed, then confirmed by a person. The declared purpose stays authoritative;
  an unconfirmed proposal never changes a verdict.
- **Phrases reach the matcher through comments.** The intent path also matches
  multi-word Annex III phrases, but only in the few lines around an AI import or
  call. About half of the labelled programs open a file with a one-line comment of
  the kind a real project writes (for example a module comment naming what the
  model scores); the other programs, and every look-alike, have none. Removing the phrase half of the matcher changes the
  intent table, which is how a regression there would show.
- **Biometric vocabulary is still broad on the default scan path.** The package
  `opencv` maps to the biometrics area whatever the program does with it, which
  is why the photo filter, the face blur and the slide-gesture controller appear
  as false positives. It stays in the list because one labelled program,
  face-attribute-categorizer, depends on it: its only face signal is
  `opencv-python` (see the table below).
- **The area 5 false positives on the default scan path came from two
  vector-index packages.** `faiss` and `pgvector` sat in the embeddings list,
  which maps to essential services whatever the program does with it. They moved
  to the machine-learning list: the program still counts as AI present, and no
  area is proposed from the package alone. The area 5 false positives on the
  intent path are a different class and were not changed.

## Signal changes in 1.3.0

The token dictionary (`ai_signals.json`) moved from version 1.2.0 to 1.3.0.
Source for every row is the benchmark fixture named in the table. Every row needs
founder review, because a token decides which Annex III area a code signal is
proposed for.

| Token | Change | Reason | Source (fixture) | Confidence | needs_founder_review |
|---|---|---|---|---|---|
| `librosa` | removed from biometric | general audio library; the area 1 false positive on a voice-feature program disappears | statement-credibility-scorer | medium | yes |
| `speaker` | removed from biometric | bare English word | none (no fixture depends on it) | medium | yes |
| `emotion` | removed from biometric | bare English word; replaced by the specific tokens below | kiosk-emotion-reader | medium | yes |
| `whisper` | moved to ml_frameworks | speech-to-text model; stays AI present, maps to no area | speech-notes, loan-calculator, interview-scorer | medium | yes |
| `speechbrain` | moved to ml_frameworks | speech toolkit; stays AI present, maps to no area | none | low | yes |
| `pyannote` | moved to ml_frameworks | audio diarisation toolkit; stays AI present, maps to no area | none | low | yes |
| `mediapipe` | moved to ml_frameworks | general vision toolkit; stays AI present, maps to no area | exam-proctor, gesture-slide-controller | low | yes |
| `emotion_recognition`, `emotion_detection`, `detect_emotion` | added to biometric | specific emotion-inference names | kiosk-emotion-reader | medium | yes |
| `fer` | added to biometric | facial-expression-recognition package; keeps the emotion reader detected once bare `emotion` is gone | kiosk-emotion-reader | medium | yes |
| `speaker_recognition`, `speaker_identification`, `speaker_verification`, `voiceprint` | added to biometric | specific voice-identification names | none | medium | yes |
| `gait_recognition` | added to biometric | specific name beside the existing `gait` | none | medium | yes |
| `faiss` | moved from vector_embedding to ml_frameworks | vector-index library; a similarity search over documents proposed essential services (area 5) on the default scan path; stays AI present, maps to no area | support-faq-bot, case-law-research-assistant | medium | yes |
| `pgvector` | moved from vector_embedding to ml_frameworks | vector-store extension; a clustering and storage job proposed essential services (area 5) on the default scan path; stays AI present, maps to no area | internal-analytics-dashboard | medium | yes |
| `opencv` | kept in biometric | face-attribute-categorizer is detected only through it (its only face signal is `opencv-python`); removing it lowers recall in area 1 | face-attribute-categorizer | medium | yes |

## Labels

Source: Annex III as encoded in the Annex III knowledge pack (area names and
sub-points). Confidence: medium. Review status: needs review (single labeller,
not legally reviewed).

## Re-run it

From a source checkout:

```bash
python packages/ai/tests/benchmark/run_benchmark.py
```

The script runs offline: the matcher is deterministic and downloads no model. It
prints both tables, the counts of clean programs, and the misses and spurious
predictions of each path.
