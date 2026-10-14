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
| 2 | critical_infrastructure | 3 | 2 | 0 | 1 | 100.0% | 66.7% |
| 3 | education | 4 | 0 | 0 | 4 | n/a | 0.0% |
| 4 | employment | 4 | 0 | 0 | 4 | n/a | 0.0% |
| 5 | essential_services | 5 | 0 | 0 | 5 | n/a | 0.0% |
| 6 | law_enforcement | 3 | 0 | 0 | 3 | n/a | 0.0% |
| 7 | migration | 3 | 0 | 0 | 3 | n/a | 0.0% |
| 8 | justice_democracy | 3 | 0 | 0 | 3 | n/a | 0.0% |
| Overall | all areas | 29 | 6 | 5 | 23 | 54.5% | 20.7% |

Programs with no Annex III area that stay clean (no area predicted): 14 of 17.

Area 2 on this path comes from one token, `write_register`, added in 1.5.0 (see
"Default-path evidence for areas 2 to 4" below); areas 3 and 4 still have no
default-path signal.

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
  area is proposed from the package alone. Six more vector-store SDKs moved the
  same way in 1.4.0 (see the 1.4.0 table below). The area 5 false positives on
  the intent path are a different class and were not changed.

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

## Signal changes in 1.4.0

The token dictionary (`ai_signals.json`) moved from version 1.3.0 to 1.4.0. The
precedent is the 1.3.0 move of `faiss` and `pgvector`, plus a re-check in which
a plain retrieval chatbot that imports a vector-store SDK read MAJOR against a
customer support declaration. Each moved token stays AI present and maps to no
area. Every row needs founder review, because a token decides which Annex III
area a code signal is proposed for. The benchmark result tables are unchanged.

| Token | Change | Reason | Source (fixture) | Confidence | needs_founder_review |
|---|---|---|---|---|---|
| `pinecone` | moved from vector_embedding to ml_frameworks | a plain retrieval chatbot read MAJOR against a customer support declaration; stays AI present, maps to no area | a retrieval chatbot re-check (reproduced by the scanner tests) | medium | yes |
| `chromadb` | moved from vector_embedding to ml_frameworks | a plain retrieval chatbot read MAJOR against a customer support declaration; stays AI present, maps to no area | a retrieval chatbot re-check (reproduced by the scanner tests) | medium | yes |
| `weaviate` | moved from vector_embedding to ml_frameworks | vector-store SDK moved by analogy with `faiss` and `pgvector`; stays AI present, maps to no area | none (no fixture) | low | yes |
| `qdrant` | moved from vector_embedding to ml_frameworks | vector-store SDK moved by analogy with `faiss` and `pgvector`; stays AI present, maps to no area | none (no fixture) | low | yes |
| `milvus` | moved from vector_embedding to ml_frameworks | vector-store SDK moved by analogy with `faiss` and `pgvector`; stays AI present, maps to no area | none (no fixture) | low | yes |
| `lancedb` | moved from vector_embedding to ml_frameworks | vector-store SDK moved by analogy with `faiss` and `pgvector`; stays AI present, maps to no area | none (no fixture) | low | yes |

## Held-out set, non-Python programs and top-1

The 46 programs above are in-sample: the token dictionary was tightened against
those same programs (see "Signal changes in 1.3.0"), so their numbers say
little about programs the dictionary has not seen. This section adds a separate
held-out set of 24 programs, a measure of the single area the classification
proposal would pick, and a 95% Wilson interval beside each rate. The held-out
numbers are the ones to read for generalisation, and they are still measured on
synthetic programs, not on real repositories.

**Labelling status.** Every held-out label comes from a single author, and the
labeller field is `author` throughout. No second pass has happened: the author's
own check is not a second review, and a person must confirm each label before
it is relied on. The set carries `needs_founder_review: true`, source "Annex
III and Article 5(1) as encoded in the knowledge pack (names, sub-points and
titles only)" and confidence medium. Each program was written from those titles
only, as a real project would name things; the keyword and code-signal fields of
the knowledge pack and the token dictionary were not read, and no program or
label was edited after a score was seen.

**What is in it.** 12 programs labelled with an Annex III area (areas 2, 4, 5
and 7 twice, the others once), 4 Article 5(1) positives with no area (points
(c), (e), (f) and (ba)), and 8 programs with no area, including a vision toolkit
that identifies nobody, a scoring model over products, a scoring model over
portfolios and a plain question-answering chatbot. 8 of the 24 are not Python:
two JavaScript, two TypeScript, two Java and two Go (Java and Go programs are
a manifest plus one source file). The programs live in
`packages/ai/tests/benchmark/heldout_fixtures.py`.

**How to read the tables.** In the set table, `n` is the number of programs in
the set and each cell shows the rate, the denominator it is taken over and the
95% interval. Precision is TP / (TP + FP) and recall is TP / (TP + FN), summed
over the eight areas as in the tables above. The top-1 table counts only
programs labelled with an area. For each one it takes the area the proposal
picks (the area with the most distinct call sites; the declared purpose is never
counted as support) and records it as correct, no proposal, a tie between areas,
or wrong. A proposal is a lead for a person to confirm, never a verdict.

| Set | Path | n | TP | FP | FN | Precision (95% CI) | Recall (95% CI) |
|---|---|---:|---:|---:|---:|---:|---:|
| Training | Intent path | 46 | 22 | 8 | 7 | 73.3% (n=30, 95% CI 55.6-85.8%) | 75.9% (n=29, 95% CI 57.9-87.8%) |
| Training | Default scan path | 46 | 6 | 5 | 23 | 54.5% (n=11, 95% CI 28.0-78.7%) | 20.7% (n=29, 95% CI 9.8-38.4%) |

| Set | Path | n | TP | FP | FN | Precision (95% CI) | Recall (95% CI) |
|---|---|---:|---:|---:|---:|---:|---:|
| Held-out | Intent path | 24 | 4 | 4 | 8 | 50.0% (n=8, 95% CI 21.5-78.5%) | 33.3% (n=12, 95% CI 13.8-60.9%) |
| Held-out | Default scan path | 24 | 1 | 3 | 11 | 25.0% (n=4, 95% CI 4.6-69.9%) | 8.3% (n=12, 95% CI 1.5-35.4%) |

Held-out programs with no area that stay clean on the intent path: 10 of 12;
on the default scan path: 9 of 12.

| Set | n | Correct | No proposal | Tie | Wrong | Top-1 accuracy (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| Training | 29 | 13 | 9 | 2 | 5 | 44.8% (n=29, 95% CI 28.4-62.5%) |
| Held-out | 12 | 1 | 9 | 1 | 1 | 8.3% (n=12, 95% CI 1.5-35.4%) |

Article 5 on the held-out set (intent path, against the `art5` label):

- `heldout_art5`: tp=1 fp=0 fn=3. One of the four prohibited-practice programs
  raised an Article 5 finding; three did not.

Area-labelled held-out programs whose area was predicted, by language (intent
path):

- `heldout_language_go`: 2 programs, 1 labelled, 0 detected.
- `heldout_language_java`: 2 programs, 2 labelled, 0 detected.
- `heldout_language_javascript`: 2 programs, 1 labelled, 0 detected.
- `heldout_language_python`: 16 programs, 7 labelled, 3 detected.
- `heldout_language_typescript`: 2 programs, 1 labelled, 1 detected.

**What the numbers say, and do not.**

- The set is small. 12 area-labelled programs and 12 top-1 trials give wide
  intervals, so read the intervals, not the point estimates, and do not compare
  two rows whose intervals overlap as if they differed.
- Java and Go programs reach the scan through their manifests only (`pom.xml`,
  `go.mod`); there is no import or call-site extraction for them. Measured
  consequence: none of the three area-labelled Java and Go programs had its
  area predicted on the intent path. The JavaScript and TypeScript programs go
  through call-site extraction; one of two area-labelled programs was
  predicted. Three programs are too few to say more. A coverage gap measured
  here is reported, not fixed.
- Four Article 5 programs are too few to estimate a rate.
- The held-out set was measured before any dictionary change and the numbers
  are pinned by the test suite. It must not be used to tune the dictionary: a
  token added or moved because of a held-out program makes this set in-sample
  too. A deliberate re-pin edits no program and no label.
- Nothing here is an accuracy claim about real repositories.

## Default-path evidence for areas 2 to 4

Before this change the default scan path predicted no program for areas 2 to 8
(0 of 25 area-labelled training programs). This section records what was
measured for areas 2, 3 and 4 and what shipped. Areas 5 to 8 are covered in
"Default-path dictionary, areas 5 to 8" below. Every number below comes from synthetic programs that one author labelled
(single-labelled, not reviewed by a second person), so none of it is an
accuracy claim about real repositories.

**Admission rule.** A token ships on the default path only if all of these hold:

- at least two distinct training programs labelled with the token's own area
  are detected through it;
- no training program with no area, and no held-out program with no area, is
  detected through it;
- default-path precision stays at or above 4/9 (44.4%) and recall at or above
  4/29 (13.8%) over the 46 training programs;
- the intent-path per-area counts and the training top-1 tuple do not move.

A token that matches one program only, a bare English word, or a name that only
one fixture's own code uses is rejected. "No token added" is an acceptable
result. The held-out programs were scanned to count hits on negatives and were
never used to pick a token; no candidate was detected in any held-out program,
labelled or not.

**Candidates.** 70 were evaluated, each on its own in a dictionary view that put
the candidate first in the `scoring` list: the 55 `code_signals` the knowledge
pack lists for areas 2, 3 and 4, 9 named domain libraries and a client method
that carry a stated source, and 6 names that occur in one training fixture only
(listed so the table shows why they do not ship). In the table, Positives is the
number of area-labelled training programs detected over the programs labelled
with that area, No-area hits is over the 17 training programs with no area, and
Held-out hits is over the 12 held-out programs with no area.

| Token | Area | Positives | No-area hits | Held-out hits | Decision | Source | Confidence | needs_founder_review |
|---|---:|---:|---:|---:|---|---|---|---|
| `traffic_control` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `grid_management` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `scada` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `power_grid` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `water_treatment` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `gas_pipeline` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `critical_infrastructure` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `safety_critical` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `plc_control` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `industrial_control` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 2 sub-point 2 | medium | yes |
| `admission_score` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(a) | medium | yes |
| `predict_admission` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(a) | medium | yes |
| `enrollment_decision` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(a) | medium | yes |
| `student_selection` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(a) | medium | yes |
| `application_rank` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(a) | medium | yes |
| `admit_student` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(a) | medium | yes |
| `reject_application` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(a) | medium | yes |
| `grade_essay` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(b) | medium | yes |
| `auto_grade` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(b) | medium | yes |
| `automated_grading` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(b) | medium | yes |
| `score_assignment` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(b) | medium | yes |
| `learning_outcome` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(b) | medium | yes |
| `predict_grade` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(b) | medium | yes |
| `education_level` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(c) | medium | yes |
| `curriculum_placement` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(c) | medium | yes |
| `learning_path` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(c) | medium | yes |
| `student_level` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(c) | medium | yes |
| `classify_student` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(c) | medium | yes |
| `proctoring` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(d) | medium | yes |
| `proctor` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(d) | medium | yes |
| `cheat_detection` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(d) | medium | yes |
| `exam_monitor` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(d) | medium | yes |
| `plagiarism_detect` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(d) | medium | yes |
| `detect_cheating` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(d) | medium | yes |
| `gaze_tracking_exam` | 3 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 3 sub-point 3(d) | medium | yes |
| `rank_candidates` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `screen_resume` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `screen_cv` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `filter_applicants` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `score_candidate` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `hiring_model` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `recruitment_model` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `shortlist_candidates` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `interview_score` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `applicant_score` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `ats_score` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(a) | medium | yes |
| `employee_score` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(b) | medium | yes |
| `performance_score` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(b) | medium | yes |
| `predict_attrition` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(b) | medium | yes |
| `termination_risk` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(b) | medium | yes |
| `promotion_model` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(b) | medium | yes |
| `worker_monitor` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(b) | medium | yes |
| `productivity_score` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(b) | medium | yes |
| `task_allocate` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(b) | medium | yes |
| `workforce_analytics` | 4 | 0/4 | 0/17 | 0/12 | rejected: no positive | Annex III pack code_signals, area 4 sub-point 4(b) | medium | yes |
| `pandapower` | 2 | 1/3 | 0/17 | 0/12 | rejected: one positive | pandapower, power-system modelling library (pandapower.org) | low | yes |
| `pymodbus` | 2 | 1/3 | 0/17 | 0/12 | rejected: one positive | pymodbus, Modbus protocol library (PyPI) | low | yes |
| `write_register` | 2 | 2/3 | 0/17 | 0/12 | accepted | pymodbus client method write_register (Modbus function code 6) | low | yes |
| `opcua` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | python-opcua, OPC UA client library (IEC 62541) | low | yes |
| `asyncua` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | asyncua, OPC UA client library (IEC 62541) | low | yes |
| `snap7` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | python-snap7, Siemens S7 PLC protocol client | low | yes |
| `pycomm3` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | pycomm3, Allen-Bradley EtherNet/IP PLC client | low | yes |
| `traci` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Eclipse SUMO traffic simulation control interface (TraCI) | low | yes |
| `sumolib` | 2 | 0/3 | 0/17 | 0/12 | rejected: no positive | Eclipse SUMO traffic network library (sumolib) | low | yes |
| `scada_link` | 2 | 0/3 | 0/17 | 0/12 | rejected: one fixture's own name | file name in grid-load-balancer, not an import | low | yes |
| `rank_applicants` | 3 | 1/4 | 0/17 | 0/12 | rejected: one fixture's own name | function name in admissions-ranker | low | yes |
| `mark_essay` | 3 | 1/4 | 0/17 | 0/12 | rejected: one fixture's own name | function name in essay-grader | low | yes |
| `rank_resumes` | 4 | 1/4 | 0/17 | 0/12 | rejected: one fixture's own name | function name in resume-screener | low | yes |
| `score_interview` | 4 | 0/4 | 0/17 | 0/12 | rejected: one fixture's own name | function name in interview-scorer | low | yes |
| `attrition_risk` | 4 | 1/4 | 0/17 | 0/12 | rejected: one fixture's own name | function name in attrition-risk | low | yes |

**Before and after, default scan path.** Measured with
`packages/ai/tests/benchmark/run_benchmark.py`, before the dictionary changed
(1.4.0) and after (1.5.0). The "after" columns equal the default-path table in
"Results" above, which is the only place the page prints that table in full:

| Area | Name | Fixtures | TP before | TP after | FP before | FP after | FN before | FN after | Precision before | Precision after | Recall before | Recall after |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | biometrics | 4 | 4 | 4 | 5 | 5 | 0 | 0 | 44.4% | 44.4% | 100.0% | 100.0% |
| 2 | critical_infrastructure | 3 | 0 | 2 | 0 | 0 | 3 | 1 | n/a | 100.0% | 0.0% | 66.7% |
| 3 | education | 4 | 0 | 0 | 0 | 0 | 4 | 4 | n/a | n/a | 0.0% | 0.0% |
| 4 | employment | 4 | 0 | 0 | 0 | 0 | 4 | 4 | n/a | n/a | 0.0% | 0.0% |
| 5 | essential_services | 5 | 0 | 0 | 0 | 0 | 5 | 5 | n/a | n/a | 0.0% | 0.0% |
| 6 | law_enforcement | 3 | 0 | 0 | 0 | 0 | 3 | 3 | n/a | n/a | 0.0% | 0.0% |
| 7 | migration | 3 | 0 | 0 | 0 | 0 | 3 | 3 | n/a | n/a | 0.0% | 0.0% |
| 8 | justice_democracy | 3 | 0 | 0 | 0 | 0 | 3 | 3 | n/a | n/a | 0.0% | 0.0% |
| Overall | all areas | 29 | 4 | 6 | 5 | 5 | 25 | 23 | 44.4% | 54.5% | 13.8% | 20.7% |

| Measurement | Before (1.4.0) | After (1.5.0) |
|---|---|---|
| Training, default path, TP / FP / FN | 4 / 5 / 25 | 6 / 5 / 23 |
| Training, default path, precision / recall | 44.4% / 13.8% | 54.5% / 20.7% |
| Training, no-area programs clean on the default path | 14 of 17 | 14 of 17 |
| Training, intent path, TP / FP / FN | 22 / 8 / 7 | 22 / 8 / 7 |
| Training top-1, correct of 29 | 13 | 13 |
| Held-out, default path, TP / FP / FN | 1 / 3 / 11 | 1 / 3 / 11 |
| Held-out, intent path, TP / FP / FN | 4 / 4 / 8 | 4 / 4 / 8 |
| Held-out top-1, correct of 12 | 1 | 1 |

**Result.** One token shipped. `write_register`, a client method of the Modbus
library `pymodbus`, is detected in two of the three area 2 training programs
(grid-load-balancer and water-treatment-dosing) and in no program with no area.
No candidate for area 3 or area 4 reached two positive programs, so no token
was added for either; the knowledge pack's `code_signals` for those areas match
none of the 46 training programs or 24 held-out programs, which is a measured
finding about the default path and not a reason to relax the rule.

**Limits of the one token.** Both positives are synthetic programs by the same
author that call the same method, so the two programs are one observation of
one idea. `write_register` is a general Modbus method name; a project that
writes Modbus registers for something that is not critical infrastructure (a
building controller, a laboratory instrument, a hobby sensor driver that names
its method the same way) would also be proposed area 2 on the default path, and
the benchmark has no program that shows how often that happens. It is a lead
for a person to confirm. The declared purpose stays authoritative and an
unconfirmed proposal never changes a verdict. The token is the first one whose
default-path detection maps to an area without the intent classifier, which is
why it needs founder review and carries confidence low.

## Signal changes in 1.5.0

The token dictionary (`ai_signals.json`) moved from version 1.4.0 to 1.5.0. A
new `area_signals` group lists tokens that map to an Annex III area on the
default scan path; each token listed there is also first in `scoring`, so it
wins over the generic tokens. The `education` and `employment` lists are empty.
The intent-path tables and the held-out tables are unchanged. Every row needs
founder review, because a token decides which Annex III area a code signal is
proposed for.

| Token | Change | Reason | Source (fixture) | Confidence | needs_founder_review |
|---|---|---|---|---|---|
| `write_register` | added to scoring (first) and to area_signals critical_infrastructure | Modbus client method for writing a register; two area 2 training programs are detected through it and no program with no area, training or held-out | grid-load-balancer, water-treatment-dosing | low | yes |

### Name spelling

The matcher treats a run of `-`, `_` and `.` as one separator and then compares
whole names, so the distribution name `face-recognition`, the module name
`face_recognition` and `Face.Recognition` are one signal. Only whole names
match: `face-recognition-lite`, `interface-recognition` and `deepfaced` do not,
and a signal shorter than four characters without a separator (`fer`) is never
matched through this rule. The rule can add a match and never removes one. It
changes no token, so the dictionary version is the same, and the tables in
"Results" above are unchanged by it.

## Default-path dictionary, areas 5 to 8

Before the dictionary work of 1.5.0 the default scan path predicted none of the
14 area-labelled training programs of areas 5 to 8 (0 of 14). This section
applies the admission rule of "Default-path evidence for areas 2 to 4" to area 5
(essential services), area 6 (law enforcement), area 7 (migration, asylum and
border control) and area 8 (justice and democratic processes). Every number below
comes from synthetic programs that one author labelled (single-labelled,
no legal review, `needs_founder_review: yes`), so none of it is an accuracy
claim about real repositories.

**Admission rule.** A token ships on the default path only if all of these hold:

- at least two distinct training programs labelled with the token's own area
  are detected through it;
- no training program with no area, and no held-out program with no area, is
  detected through it;
- the token maps to exactly one area and matches no Article 5 signal;
- default-path precision stays at or above 4/9 (44.4%) and recall at or above
  4/29 (13.8%) over the 46 training programs, and the intent-path counts do not
  move.

Positives are counted on the 46 training programs only. The held-out programs
are scanned for the zero-hit check on negatives and are reported, never used to
pick a token. "No token added" is an acceptable result.

**Candidates.** 274 forms were evaluated, each on its own in a dictionary view
that put the form first in the `scoring` list and listed it under its area key.
A form is a multi-word phrase of the knowledge pack for the area (its title,
keywords and code signals) written as one identifier (`credit score` becomes
`credit_score`), kept only when the spaced phrase maps to exactly that one area
and matches no Article 5 signal: 98 forms for area 5, 78 for area 6, 55 for area
7 and 43 for area 8. In the table, Forms considered is that count, With fixture
hits is the number of forms detected in at least one training program, Positives
is the number of area-labelled training programs detected through any form of
the area, and No-area hits is the number of programs with no area (17 training
and 12 held-out) detected through any form of the area.

| Area | Forms considered | With fixture hits | Positives | No-area hits | Decision |
|---:|---:|---:|---:|---:|---|
| 5 | 98 | 1 | 1/5 | 3/29 | no token added |
| 6 | 78 | 0 | 0/3 | 0/29 | no token added |
| 7 | 55 | 0 | 0/3 | 0/29 | no token added |
| 8 | 43 | 0 | 0/3 | 0/29 | no token added |

**Before and after, default scan path.** The runner output of
`packages/ai/tests/benchmark/run_benchmark.py` for the default scan path, at the
start of this change and after it. The dictionary is unchanged, so the two blocks
are identical.

=== "Before (dictionary 1.5.0)"

    ```text
    Default scan path
    | Area | Name | Fixtures | TP | FP | FN | Precision | Recall |
    |---|---|---:|---:|---:|---:|---:|---:|
    | 1 | biometrics | 4 | 4 | 5 | 0 | 44.4% | 100.0% |
    | 2 | critical_infrastructure | 3 | 2 | 0 | 1 | 100.0% | 66.7% |
    | 3 | education | 4 | 0 | 0 | 4 | n/a | 0.0% |
    | 4 | employment | 4 | 0 | 0 | 4 | n/a | 0.0% |
    | 5 | essential_services | 5 | 0 | 0 | 5 | n/a | 0.0% |
    | 6 | law_enforcement | 3 | 0 | 0 | 3 | n/a | 0.0% |
    | 7 | migration | 3 | 0 | 0 | 3 | n/a | 0.0% |
    | 8 | justice_democracy | 3 | 0 | 0 | 3 | n/a | 0.0% |
    | Overall | all areas | 29 | 6 | 5 | 23 | 54.5% | 20.7% |

    scan_none_clean: 14 of 17
    ```

=== "After (dictionary 1.5.0)"

    ```text
    Default scan path
    | Area | Name | Fixtures | TP | FP | FN | Precision | Recall |
    |---|---|---:|---:|---:|---:|---:|---:|
    | 1 | biometrics | 4 | 4 | 5 | 0 | 44.4% | 100.0% |
    | 2 | critical_infrastructure | 3 | 2 | 0 | 1 | 100.0% | 66.7% |
    | 3 | education | 4 | 0 | 0 | 4 | n/a | 0.0% |
    | 4 | employment | 4 | 0 | 0 | 4 | n/a | 0.0% |
    | 5 | essential_services | 5 | 0 | 0 | 5 | n/a | 0.0% |
    | 6 | law_enforcement | 3 | 0 | 0 | 3 | n/a | 0.0% |
    | 7 | migration | 3 | 0 | 0 | 3 | n/a | 0.0% |
    | 8 | justice_democracy | 3 | 0 | 0 | 3 | n/a | 0.0% |
    | Overall | all areas | 29 | 6 | 5 | 23 | 54.5% | 20.7% |

    scan_none_clean: 14 of 17
    ```

**Result.** No token was added for area 5, 6, 7 or 8. Of the 274 forms, one
was detected in any training program: `predict_proba`, a method name the
knowledge pack lists among its essential-services code signals. It is detected
in 11 training programs (one labelled area 5, two with no area, eight labelled
with another area) and in one held-out program with no area, so it fails the
zero-hit rule and is not shipped. The other 273 forms match none of the 46
training programs or 24 held-out programs. That is a measured finding about the
default path, and not a reason to relax the rule. No row is added to the
signal-change tables, no dictionary version is bumped and no pin moved.

**What this means.** A token reaches an area on the default scan path only
through the `area_signals` group of the dictionary: a single-word label never
fires an area alone, a specific token placed after a generic scoring token such as
`score` is shadowed by it, and a token left out of the group is unmapped. The
intent path (`scan --ai-intent`) is the route that reaches areas 5 to 8 today
(see "Intent path" above). A program's area on the default path is a lead for a
person to confirm; the declared purpose stays authoritative.

## Signal changes in 1.6.0

The token dictionary (`ai_signals.json`) moved from version 1.5.0 to 1.6.0.
Five generic embedding tokens left `vector_embedding`, which maps to essential
services (area 5), and joined `ml_frameworks`, which counts as AI usage and maps
to no area. The intent-path tables, the held-out tables and the default-path
tables are unchanged. Every row needs founder review.

| Token | Change | Reason | Source (fixture) | Confidence | needs_founder_review |
|---|---|---|---|---|---|
| `voyageai` | moved from vector_embedding to ml_frameworks | an embedding client says nothing about the purpose; a plain retrieval chatbot raised area 5 through it | plain retrieval chatbot, re-check | medium | yes |
| `jina` | moved from vector_embedding to ml_frameworks | same as `voyageai` | plain retrieval chatbot, re-check | medium | yes |
| `embedding` | moved from vector_embedding to ml_frameworks | `get_embedding` or `embedding_model` is a generic call name; a plain retrieval chatbot raised area 5 through it | plain retrieval chatbot, re-check | medium | yes |
| `rerank` | moved from vector_embedding to ml_frameworks | a re-ranking call is part of retrieval, not a decision about a person | plain retrieval chatbot, re-check | medium | yes |
| `similarity_search` | moved from vector_embedding to ml_frameworks | a vector search method name; a plain retrieval chatbot raised area 5 through it | plain retrieval chatbot, re-check | medium | yes |

## Generic token review in 1.6.0

Each token left in the embedding and personal-data groups after the vector-store
SDK change was re-checked with a plain retrieval chatbot (declared purpose
"customer support chatbot", one call to the OpenAI SDK, one use of the token, no
scoring word). Before the move, each of the five embedding tokens proposed
essential services and read MAJOR; after it, none does and each still counts as
AI usage. The seven personal-data hints stay where they are: they fire only next
to a model call, and area 5 from personal data near a model call is the category
mapping, a decision outside this review. A re-measurement of the benchmark gave
the same numbers before and after.

| Token | Group | Plain-retrieval result | Decision | Reason | Source | Confidence | needs_founder_review |
|---|---|---|---|---|---|---|---|
| `voyageai` | vector_embedding | area 5, MAJOR | moved | no intent signal; still AI usage | plain retrieval chatbot, re-check | medium | yes |
| `jina` | vector_embedding | area 5, MAJOR | moved | no intent signal; still AI usage | plain retrieval chatbot, re-check | medium | yes |
| `embedding` | vector_embedding | area 5, MAJOR | moved | no intent signal; still AI usage | plain retrieval chatbot, re-check | medium | yes |
| `rerank` | vector_embedding | area 5, MAJOR | moved | no intent signal; still AI usage | plain retrieval chatbot, re-check | medium | yes |
| `similarity_search` | vector_embedding | area 5, MAJOR | moved | no intent signal; still AI usage | plain retrieval chatbot, re-check | medium | yes |
| `email` | pii_hints | not raised without a personal-data word | kept | moving it would make the standard `email` package an AI library | dictionary review | low | yes |
| `ssn` | pii_hints | not raised without a personal-data word | kept | documented personal-data hint near a model call | dictionary review | low | yes |
| `passport` | pii_hints | not raised without a personal-data word | kept | documented personal-data hint near a model call | dictionary review | low | yes |
| `patient_id` | pii_hints | not raised without a personal-data word | kept | documented personal-data hint near a model call | dictionary review | low | yes |
| `phi` | pii_hints | not raised without a personal-data word | kept | documented personal-data hint near a model call | dictionary review | low | yes |
| `pii` | pii_hints | not raised without a personal-data word | kept | documented personal-data hint near a model call | dictionary review | low | yes |
| `biometric_id` | pii_hints | not raised without a personal-data word | kept | documented personal-data hint near a model call | dictionary review | low | yes |

## Candidates (leads, not findings)

A candidate is a lead for a person. It points at an AI library that production
code imports but that yields no Annex III signal. It is not a finding. It is
never part of the gate, the classification proposal, any exit code, or the
precision and recall tables above: candidates are excluded from precision and
recall, and measuring them leaves those tables as they are.

They are counted separately, on the intent path only, over a small set of
synthetic programs in `packages/ai/tests/benchmark/candidate_fixtures.py`. The
set holds import-only programs of each named library and programs that must
yield no candidate: one whose library is a finding, requirements-only
dependencies in two spellings, look-alike names and an import under `tests/`.
The table counts, per library, the programs in which a candidate was reported
and the candidates reported; the last row counts every program of the set. It
has no precision or recall column and is not an accuracy figure.

| Library | Fixtures | Candidates |
|---|---:|---:|
| facenet_pytorch | 1 | 1 |
| mtcnn | 1 | 1 |
| retinaface | 1 | 1 |
| all libraries | 8 | 3 |

The programs are synthetic and were labelled by one author, with confidence low
and `needs_founder_review: true`. They show that the rule reports what it was
written to report. They say nothing about how often a real repository imports
such a library, or whether a person would call it a classification.

## Leads on the three sets

A lead is a pointer for a person to review. It is not a finding: it has no
severity, it never changes an exit code, and it is not part of the signed
artifact or of the classification proposal. When the optional plugin is
installed, `scan`, `scan --quick` and `check --scan` print leads for Annex III
areas 3, 4, 5, 6 and 8; area 7 is notice only. Each lead is one call site that the deterministic matcher put in
an area; a call site whose area comes only from the declared purpose is the
manifest talking back, and is not a lead.

This section measures those leads on three labelled sets: the training set and
the held-out set above, and a separate set of programs for areas 3 to 8 that was
recorded before any lead tier existed and is never tuned against. All three sets
are synthetic and were labelled by a single author, with confidence low and
`needs_founder_review: true`. A program counts as led for an area when at least
one of its call sites is a lead for that area. TP, FP and FN read as above, over
areas 3 to 8 only: areas 1 and 2 never produce a lead and are not scored. The
`Programs` column counts the programs labelled with the area.

Training set:

| Set | Area | Name | Programs | TP | FP | FN | Precision | Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Lead tier training | 3 | education | 4 | 2 | 0 | 2 | 100.0% | 50.0% |
| Lead tier training | 4 | employment | 4 | 2 | 0 | 2 | 100.0% | 50.0% |
| Lead tier training | 5 | essential_services | 5 | 4 | 8 | 1 | 33.3% | 80.0% |
| Lead tier training | 6 | law_enforcement | 3 | 2 | 0 | 1 | 100.0% | 66.7% |
| Lead tier training | 7 | migration | 3 | 0 | 0 | 3 | n/a | 0.0% |
| Lead tier training | 8 | justice_democracy | 3 | 2 | 0 | 1 | 100.0% | 66.7% |
| Lead tier training | Overall | areas 3 to 8 | 22 | 12 | 8 | 10 | 60.0% | 54.5% |

Held-out set:

| Set | Area | Name | Programs | TP | FP | FN | Precision | Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Lead tier held-out | 3 | education | 1 | 0 | 0 | 1 | n/a | 0.0% |
| Lead tier held-out | 4 | employment | 2 | 0 | 0 | 2 | n/a | 0.0% |
| Lead tier held-out | 5 | essential_services | 2 | 0 | 3 | 2 | 0.0% | 0.0% |
| Lead tier held-out | 6 | law_enforcement | 1 | 1 | 0 | 0 | 100.0% | 100.0% |
| Lead tier held-out | 7 | migration | 2 | 0 | 0 | 2 | n/a | 0.0% |
| Lead tier held-out | 8 | justice_democracy | 1 | 0 | 0 | 1 | n/a | 0.0% |
| Lead tier held-out | Overall | areas 3 to 8 | 9 | 1 | 3 | 8 | 25.0% | 11.1% |

Areas 3 to 8 set:

| Set | Area | Name | Programs | TP | FP | FN | Precision | Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Lead tier areas 3-8 | 3 | education | 3 | 0 | 0 | 3 | n/a | 0.0% |
| Lead tier areas 3-8 | 4 | employment | 3 | 0 | 0 | 3 | n/a | 0.0% |
| Lead tier areas 3-8 | 5 | essential_services | 4 | 0 | 2 | 4 | 0.0% | 0.0% |
| Lead tier areas 3-8 | 6 | law_enforcement | 3 | 0 | 0 | 3 | n/a | 0.0% |
| Lead tier areas 3-8 | 7 | migration | 3 | 0 | 0 | 3 | n/a | 0.0% |
| Lead tier areas 3-8 | 8 | justice_democracy | 3 | 0 | 0 | 3 | n/a | 0.0% |
| Lead tier areas 3-8 | Overall | areas 3 to 8 | 19 | 0 | 2 | 19 | 0.0% | 0.0% |

### The floor and the policy

The floor is the precision of the intent path overall on the training set: the
intent-path table above has 22 true positives among 30 predictions (TP and FP
together). A lead needs precision at or above it, checked as the exact
fraction `TP * 30 >= 22 * (TP + FP)`. The decision on the leads floor leaves
four points open; this page takes the conservative reading of each, and each is
`needs_founder_review: true`:

- The figure of an area is pooled over the three sets, because each set alone
  has few programs per area.
- An area with no true positive on the pool has no evidence of precision and
  shows notice only.
- Area 5 is shown regardless of the floor, always at the lowest confidence, and
  is left out of the decision for the whole feature. Its figures are still
  printed.
- Leads are on by default only when the pool of the areas other than 5 meets
  the floor.

`lead` means leads are shown for the area. `notice_only` means no lead is shown
and the scan prints the default-scan coverage notice only. `lowest_confidence`
means leads are shown, always at the lowest confidence band.

| Set | Area | Name | Programs | TP | FP | FN | Precision | Recall | Policy |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Lead tier pooled | 3 | education | 8 | 2 | 0 | 6 | 100.0% | 25.0% | lead |
| Lead tier pooled | 4 | employment | 9 | 2 | 0 | 7 | 100.0% | 22.2% | lead |
| Lead tier pooled | 5 | essential_services | 11 | 4 | 13 | 7 | 23.5% | 36.4% | lowest_confidence |
| Lead tier pooled | 6 | law_enforcement | 7 | 3 | 0 | 4 | 100.0% | 42.9% | lead |
| Lead tier pooled | 7 | migration | 8 | 0 | 0 | 8 | n/a | 0.0% | notice_only |
| Lead tier pooled | 8 | justice_democracy | 7 | 2 | 0 | 5 | 100.0% | 28.6% | lead |
| Lead tier pooled | Overall | areas 3 to 8 | 50 | 13 | 13 | 37 | 50.0% | 26.0% | - |
| Lead tier pooled | Overall without 5 | areas 3, 4, 6, 7, 8 | 39 | 9 | 0 | 30 | 100.0% | 23.1% | on by default |

The policy that follows from the pooled table:

| Area | Policy | Source | Confidence | needs_founder_review |
|---|---|---|---|---|
| 3 | `lead` | round decision on the leads floor, heuristic | low | yes |
| 4 | `lead` | round decision on the leads floor, heuristic | low | yes |
| 5 | `lowest_confidence` | round decision on the leads floor, heuristic | low | yes |
| 6 | `lead` | round decision on the leads floor, heuristic | low | yes |
| 7 | `notice_only` | round decision on the leads floor, heuristic | low | yes |
| 8 | `lead` | round decision on the leads floor, heuristic | low | yes |

The pool of the areas other than 5 meets the floor, so leads are on by default.
`OPENCOMPLAI_LEADS=0` (or `false`, `off`) turns them off; `OPENCOMPLAI_LEADS=1`
(or `true`, `on`) turns them on.

Top-1 is the area the classification proposal picks for each program labelled
with an area, scored as in the held-out section above. It is the same
measurement as the proposal top-1 tables, listed here per set.

| Lead tier set | n | Correct | No proposal | Tie | Wrong | Top-1 accuracy (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| Lead tier training | 29 | 13 | 9 | 2 | 5 | 44.8% (n=29, 95% CI 28.4-62.5%) |
| Lead tier held-out | 12 | 1 | 9 | 1 | 1 | 8.3% (n=12, 95% CI 1.5-35.4%) |
| Lead tier areas 3-8 | 19 | 0 | 17 | 0 | 2 | 0.0% (n=19, 95% CI 0.0-16.8%) |

Read these numbers with the floor in mind. The pooled precision of the areas
other than 5 is carried by the training set, the set the signal dictionary was
tightened against (see the signal-change sections above). On the areas 3 to 8
set alone, no lead matched a label, and the leads that did appear were for
area 5. The figures say how the leads behave on synthetic programs written by
one author; they say nothing about how often a real repository gets a useful
lead.

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
predictions of each path. It also prints the held-out and top-1 tables, then the
leads section (a table per set, the pooled table with the policy per area, and
the top-1 table), and ends with the candidates section, which holds counts per
library and no precision or recall.
