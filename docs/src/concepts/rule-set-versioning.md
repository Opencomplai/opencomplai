# Rule-set versioning

Every verdict Opencomplai prints is produced by a set of rules, keyword lists and data files. The
**rule-set version** names that set, so two runs can be compared and a change in verdicts can be traced
to a change in the rules rather than in your system.

## What it is

`RULE_SET_VERSION` is a dotted version string defined in `opencomplai_core/rules.py`. It moves when any
rule logic, keyword list or article reference changes. It is stamped into:

- every generated Annex IV dossier, as the rule set the assessment used;
- the `compliance-artifact.json` written by `opencomplai check`, as `rule_set_version`.

The history behind the number is a data file, `ruleset_history.json`, read oldest to newest. The last
entry is always the current version, and a test keeps the two in step.

| Field of a history entry | Meaning |
|---|---|
| `version` | The rule-set version. |
| `summary` | One line on what the version is. |
| `changes` | One bullet per semantic change that shipped in it. |
| `source` | Where the description comes from. |
| `confidence` | How sure the entry is. |
| `needs_founder_review` | `true` when the entry is awaiting human review. |

Earlier versions are not all reconstructed in the file, and an entry says so when that is the case; do not
read a gap in the list as "nothing changed".

## Reading the history

[`opencomplai rules changelog`](../cli/rules.md) prints the entries with their `source`, `confidence` and
review flag exactly as stored. `--since 1.5.0` limits it to newer versions. It is read-only.

[`opencomplai diff`](../cli/diff.md) compares two runs. When both inputs carry a `rule_set_version`, it
says whether the rules changed and lists the history entries between the two. When either side has none
(a gap report or a `gaps` envelope never carries one), the rule set is reported as unknown and nothing is
claimed either way. A changed verdict next to a changed rule-set version is the first thing to check before
treating it as a regression in your system.

## Three version numbers, three meanings

| Name | Where you see it | What it identifies |
|---|---|---|
| Rule-set version | `rule_set_version` in the artifact and dossier; `rules changelog` | The rules, keyword lists and mappings that produce the EU AI Act verdicts. |
| Data version | `data_version` on a framework report in [`gaps`](../cli/gaps.md) JSON and in the artifact's `framework_reports` | A short hash of one framework's data files. Two reports with the same value used the same mappings. See [Frameworks](../frameworks/index.md). |
| Schema version | `schema_version` in the artifact; the `/v<major>` suffix of a schema `$id` | The shape of the file. See [Published schemas](published-schemas.md). |

The three move independently. A new rule can change a verdict without changing the schema, and a new
optional field can widen the schema without touching a rule. `check` also stamps `cli_version` and
`manifest_sha256` before signing, so a signed artifact says which tool and which manifest produced it.

## What the version does not do

It does not change an exit code by itself, and it is not a legal statement about which rules were in force
on a given date. Exit codes are described in [Exit codes](../cli/exit-codes.md); the history entries carry
their own `source`, `confidence` and review flag, and are only as reliable as those fields say.
