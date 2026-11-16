# Framework gates

Gate a pull request on one framework. Each registered framework has a ready-to-copy
`opencomplai.yaml` in [`examples/framework-gates`](https://github.com/Opencomplai/opencomplai/tree/main/examples/framework-gates).

## Pick the framework

Print the registered keys:

```
uv run python -c "from opencomplai_core.frameworks import FRAMEWORKS; print('\n'.join(FRAMEWORKS))"
```

Pick the folder named after the key, for example `examples/framework-gates/ISO_IEC_42001/`.

`EU_AI_ACT` is refused as a gate framework, because its rules gate already. Exit 3 (prohibited
practice) and exit 4 (modification trap) exist for the EU AI Act alone. A gated row from any other
framework turns a pass into exit 1.

## The opencomplai.yaml file

Copy the file to the repository root:

```yaml
# Gate example for ISO_IEC_42001.
# A framework row that is Missing fails `opencomplai check` with exit 1.
# Copy this file to the repository root as opencomplai.yaml.
gate:
  frameworks: [ISO_IEC_42001]
  fail_on: missing
```

`fail_on` takes `missing`, `partial` or `unverified`. The `EU_AI_ACT` example has no `gate`
section and sets `scan: {fail_on: major}` instead.

The same gate is available as flags on [`check`](../cli/check.md):

| Flag | Meaning |
|---|---|
| `--gate <KEY>` | Gate on this framework. |
| `--gate-fail-on <level>` | `missing`, `partial` or `unverified`. |
| `--with-gaps` | Add the per-article gap report. |
| `--report-junit <file>` | Write a JUnit report. |
| `--sarif-output <file>` | Write a SARIF report. |
| `--summary-md <file>` | Write a Markdown summary. |

## GitHub Actions

Use the [GitHub Action](github-action.md) with its `args` input:

```yaml
- uses: Opencomplai/opencomplai-action@<40-hex commit SHA> # v1
  with:
    manifest: system-manifest.json
    args: --with-gaps --gate ISO_IEC_42001 --gate-fail-on missing
```

Replace `ISO_IEC_42001` with your key. The job fails when the gate exits 1.

## GitLab CI

```yaml
framework-gate:
  image: python:3.12
  script:
    - pip install opencomplai
    - opencomplai check --with-gaps --report-junit report.xml --sarif-output results.sarif
  artifacts:
    when: always
    reports:
      junit: report.xml
    paths:
      - results.sarif
```

The `opencomplai.yaml` at the repository root carries the gate, so the command needs no
`--gate` flag.

## Reading JUnit and SARIF

JUnit and SARIF carry one entry per failed framework row. In JUnit each failed row is a failed
test case; in SARIF each is one result. A pull request that gates on a framework with three
Missing rows shows three entries.

## What a gate does not tell you

A Partial or Missing row is a finding about files in the repository, not a legal assessment. A
passing gate means no row reached the `fail_on` level; it does not say the system meets any law
or standard. Ask your adviser for that.
