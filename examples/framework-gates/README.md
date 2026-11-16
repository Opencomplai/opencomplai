# Framework gate examples

One folder per registered framework, each with a ready-to-copy `opencomplai.yaml`. Copy the
file to the root of your repository, then run the command below from there.

```
opencomplai check --with-gaps --report-junit report.xml --sarif-output results.sarif
```

| Key | File |
|---|---|
| `EU_AI_ACT` | [`EU_AI_ACT/opencomplai.yaml`](EU_AI_ACT/opencomplai.yaml) |
| `NIST_AI_RMF` | [`NIST_AI_RMF/opencomplai.yaml`](NIST_AI_RMF/opencomplai.yaml) |
| `ISO_IEC_42001` | [`ISO_IEC_42001/opencomplai.yaml`](ISO_IEC_42001/opencomplai.yaml) |
| `ISO_IEC_27090` | [`ISO_IEC_27090/opencomplai.yaml`](ISO_IEC_27090/opencomplai.yaml) |
| `ISO_IEC_27001` | [`ISO_IEC_27001/opencomplai.yaml`](ISO_IEC_27001/opencomplai.yaml) |
| `SOC_2` | [`SOC_2/opencomplai.yaml`](SOC_2/opencomplai.yaml) |
| `NIS2` | [`NIS2/opencomplai.yaml`](NIS2/opencomplai.yaml) |
| `DORA` | [`DORA/opencomplai.yaml`](DORA/opencomplai.yaml) |
| `EBA` | [`EBA/opencomplai.yaml`](EBA/opencomplai.yaml) |
| `EIOPA_AI` | [`EIOPA_AI/opencomplai.yaml`](EIOPA_AI/opencomplai.yaml) |
| `GDPR` | [`GDPR/opencomplai.yaml`](GDPR/opencomplai.yaml) |
| `CRA` | [`CRA/opencomplai.yaml`](CRA/opencomplai.yaml) |
| `ETSI_EN_304_223` | [`ETSI_EN_304_223/opencomplai.yaml`](ETSI_EN_304_223/opencomplai.yaml) |
| `ISO_IEC_42005` | [`ISO_IEC_42005/opencomplai.yaml`](ISO_IEC_42005/opencomplai.yaml) |
| `ISO_IEC_23894` | [`ISO_IEC_23894/opencomplai.yaml`](ISO_IEC_23894/opencomplai.yaml) |

Every key except `EU_AI_ACT` gates on `fail_on: missing`. `EU_AI_ACT` has no `gate` section,
because its rules gate already; its example sets `scan: {fail_on: major}`.

A Missing or Partial row is a finding about files in the repository, not a legal assessment.
See the [guide](../../docs/src/guides/framework-gates.md).
