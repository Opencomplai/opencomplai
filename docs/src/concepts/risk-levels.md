# Risk levels

Opencomplai reports one of four EU AI Act-aligned risk levels for every assessed system.

## The four levels

| Level | `RiskLevel` enum | EU AI Act basis | Typical `ScanResult` |
|---|---|---|---|
| Unacceptable | `UNACCEPTABLE` | Title II (Art. 5) — prohibited practices | `policy_block` |
| High | `HIGH` | Title III (Art. 6 + Annex III) — high-risk systems | `control_fail` (if controls incomplete) |
| Limited | `LIMITED` | Art. 52 — transparency obligations | `pass` with transparency controls |
| Minimal | `MINIMAL` | All other AI systems | `pass` |

## Level definitions

### Unacceptable

AI practices that are prohibited outright under the EU AI Act. Examples include real-time remote biometric identification in public spaces, social scoring by public authorities, and systems that exploit psychological vulnerabilities. `opencomplai check` will return exit code `3` (`POLICY_BLOCK`) if a system is classified as unacceptable risk.

### High

Systems listed in **Annex III** of the EU AI Act, such as AI used in:

- Critical infrastructure (energy, water, transport)
- Educational and vocational training
- Employment and worker management
- Essential private and public services (credit scoring, social benefits)
- Law enforcement
- Migration, asylum, and border control
- Administration of justice

High-risk systems must comply with obligations in Title III Chapter 2 (risk management, data governance, technical documentation, human oversight, accuracy, robustness, and cybersecurity).

### Limited

Systems subject to transparency obligations under Art. 52 — e.g., chatbots that must disclose they are AI, deep-fake generators that must watermark outputs.

### Minimal

All other AI systems. Compliance is recommended but not mandated.

## How the rule engine assigns risk

The rule `EU_AIA_ART6_HIGH_RISK` evaluates `intended_purpose` and `high_risk_presumption` from the system manifest against the Annex III category list. If `high_risk_presumption` is `True`, the system is classified as `high` regardless of `intended_purpose`.

## Python enum reference

```python
from opencomplai_core.models import RiskLevel

RiskLevel.UNACCEPTABLE  # "unacceptable"
RiskLevel.HIGH          # "high"
RiskLevel.LIMITED       # "limited"
RiskLevel.MINIMAL       # "minimal"
```
