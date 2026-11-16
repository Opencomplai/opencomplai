## Opencomplai Compliance Scan

| Field | Value |
|-------|-------|
| Result | `control_fail` |
| System | `pack-golden-sys` |
| Commit | `unresolved` |
| Signed | `no (unsigned artifact)` |
| Failed controls | `ISO_IEC_27090: 19 requirement(s)` |

### ISO/IEC 27090:2026 AI security guidance (evaluated, guidance, not a certification)

| Requirement | Title | Status | Evidence |
|-------------|-------|--------|----------|
| ISO_IEC_27090:5.2 | AI governance programme | missing | policy_ai |
| ISO_IEC_27090:5.3 | Zero trust principles | missing | iso_iec_27090.model_access_control |
| ISO_IEC_27090:5.4 | Applying software engineering best practices to AI | missing | sast_config |
| ISO_IEC_27090:5.5 | Supply chain management | missing | ai_supply_chain_pins |
| ISO_IEC_27090:5.6 | Threat modelling | missing | ai_threat_model |
| ISO_IEC_27090:5.7 | Red teaming | missing | ai_red_team_report |
| ISO_IEC_27090:6.2 | Data poisoning attack | missing | data_provenance_sheet |
| ISO_IEC_27090:6.3 | Evasion attack | missing | ai_red_team_report |
| ISO_IEC_27090:6.5 | Model exfiltration | missing | rate_limiting_config |
| ISO_IEC_27090:6.7 | Direct model poisoning | missing | ai_supply_chain_pins |
| ISO_IEC_27090:6.10 | Output contains injection attacks | missing | iso_iec_27090.input_validation_config |
| ISO_IEC_27090:7.4 | Model and mitigation deterioration over time | missing | post_market_monitoring_plan |
| ISO_IEC_27090:7.5 | Logging and monitoring | missing | event_log_evidence |
| ISO_IEC_27090:7.7 | Malicious input detection and filtering | missing | iso_iec_27090.input_validation_config |
| ISO_IEC_27090:7.8 | Throttling model use | missing | rate_limiting_config |
| ISO_IEC_27090:B.2 | Denial-of-service attacks (provisional numbering) | missing | rate_limiting_config |
| ISO_IEC_27090:B.3 | Supply chain attacks (provisional numbering) | missing | ai_supply_chain_pins |
| ISO_IEC_27090:B.4 | Backdoor attacks (provisional numbering) | missing | ai_supply_chain_pins |
| ISO_IEC_27090:B.5 | Direct model theft (provisional numbering) | missing | iso_iec_27090.model_access_control |
