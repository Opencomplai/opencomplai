# EU AI Act

## What it is

Regulation (EU) 2024/1689 sets rules for AI systems placed on the EU market or put into
service there: practices that are prohibited, obligations for high-risk systems,
transparency duties, and duties for providers of general-purpose AI models. Opencomplai
carries it as the native target `EU_AI_ACT`, and it is the reference pack: the other
framework packs are built on the same outline as this page.

The pack has 24 rows, one per article the gap report speaks to. Its status is
`evaluated`: the rows are decided from evidence the tool reads, not only from what you
declare. No tool writes that status. The page describes evidence found. It does not
say that a system meets the law.

## Does it apply to you

Whether, and in which role, the Act reaches your system is decided by the applicability
checker, not by this page. Run it first: see the
[EU AI Act checker](../getting-started/eu-ai-act-checker.md). Its answers decide which
obligations are in play, and some rows below only apply for a given role or risk tier.
A row that does not apply to you is reported as not applicable, not as missing.

## How rows are decided

Each row names one or more sources: a rule result, an evaluator, a scan signal, a
manifest declaration, an artifact in the repository, or an attestation. A row takes the
worst status of the sources that apply, and reads `Met`, `Partial`, `Missing` or
`Unverified`. The reasoning behind the sources is in
[EU AI Act principles](../concepts/eu-ai-act-principles.md).

22 of the 24 rows have a source other than an attestation. An attestation can still sit
beside those sources, but it is not the only thing deciding the row. Percentages derived
from rows are a draft estimate.

## Requirements

The table lists the 24 rows with the kinds of source that decide each one. `pack_doc.py` cannot write it for this pack, so it is kept by hand from the pack's article map.

<!-- rows:start -->
| Article | Title | Source kinds |
| --- | --- | --- |
| Art. 4 | AI literacy | attestation |
| Art. 5 | Prohibited AI practices | obligation, rule |
| Art. 6 | Classification of high-risk systems | rule, scan |
| Art. 9 | Risk management system | artifact, obligation |
| Art. 10 | Data and data governance | evaluator, scan |
| Art. 11 | Technical documentation | artifact |
| Art. 12 | Record-keeping | artifact, manifest |
| Art. 13 | Transparency and information to deployers | artifact, manifest |
| Art. 14 | Human oversight | artifact, manifest, scan |
| Art. 15 | Accuracy, robustness and cybersecurity | evaluator, manifest, scan |
| Art. 16 | Obligations of providers of high-risk systems | artifact |
| Art. 17 | Quality management system | artifact |
| Art. 20 | Corrective actions and duty of information | attestation |
| Art. 24 | Obligations of distributors | artifact |
| Art. 25 | Responsibilities along the AI value chain | rule |
| Art. 26 | Obligations of deployers of high-risk systems | artifact, manifest |
| Art. 27 | Fundamental rights impact assessment | artifact, obligation |
| Art. 43 | Conformity assessment | artifact |
| Art. 49 | Registration | artifact, record |
| Art. 50 | Transparency obligations for certain systems | artifact, obligation |
| Art. 53 | Obligations of providers of general-purpose AI models | artifact, obligation |
| Art. 55 | Obligations for general-purpose models with systemic risk | artifact, obligation |
| Art. 72 | Post-market monitoring | artifact |
| Art. 73 | Reporting of serious incidents | artifact |
<!-- rows:end -->

## Scaffolds

Several rows ask for a document that you write and keep. The generator commands draft a
starting point from your manifest:

| Command | Drafts |
| --- | --- |
| `opencomplai docs generate` | The Annex IV technical documentation dossier (Art. 11) |
| `opencomplai qms generate` | The Art. 17 quality management system document |
| `opencomplai instructions generate` | Instructions for use (Art. 13) |
| `opencomplai fria generate` | A fundamental rights impact assessment (Art. 27) |

`opencomplai deployer-pack build` seals an instructions-for-use document so a deployer
can import it. A draft is a scaffold for a person to complete and review, not a finished
document. The [Annex IV coverage ledger](../concepts/annex-iv-coverage.md) states which
parts of the dossier are measured, which are declared by you and which stay placeholders.

## Timeline

Different parts of the Act apply from different points in time, and some of those points
have moved by amendment. The tool keeps them in one data file of dated entries, each with
the articles it covers and a confidence note, and reads that file when it decides which
rows are in force. This page gives no dates: take them from the tool's output and check
them against the text of the Regulation as published in the Official Journal.

## Gate in CI

`opencomplai check` can fail a build. For this framework alone the gate has risk tiers
and two dedicated exit codes:

| Exit code | Meaning |
| --- | --- |
| `1` | A control fails, for example a high-risk classification |
| `3` | Policy block: a prohibited practice (Art. 5) was found |
| `4` | Modification trap: a declared change context trips the Art. 25 substantial-modification rule |

Every other framework pack fails a gate with exit code `1` and has no risk tiers.

## What stays attested and why

Two rows have no source other than an attestation:

- **Art. 4** (AI literacy): the measures concern your staff and the people who work with
  the system, and nothing in a repository shows them.
- **Art. 20** (corrective actions and the duty of information): whether you took
  corrective action when a system did not conform is a fact about your organisation, not
  about code.

An attestation names who vouches for the statement and when, and it expires. It reads
`Met`, labelled `attested`, only while it is current.

## Review status

The rows, source choices and applicability notes are draft content. Several carry low
confidence and are marked for review by a lawyer. Treat the table as a map of evidence to
look for, not as legal advice.

## Disclaimer

Opencomplai reports evidence it found against a list of requirements. It does not
assess a system for you, and nothing on this page or in its output is a legal opinion or
a statement that a system satisfies the Regulation. Take legal advice for your own case.
