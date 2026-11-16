## Opencomplai Compliance Scan

| Field | Value |
|-------|-------|
| Result | `control_fail` |
| System | `pack-golden-sys` |
| Commit | `unresolved` |
| Signed | `no (unsigned artifact)` |
| Failed controls | `ETSI_EN_304_223: 46 requirement(s)` |

### ETSI EN 304 223 baseline cyber security for AI (evaluated, not an audit, certification or legal assessment)

| Requirement | Title | Status | Evidence |
|-------------|-------|--------|----------|
| ETSI_EN_304_223:5.1.1-1 | P1 Awareness: AI content in security training | missing | competence_training_record |
| ETSI_EN_304_223:5.1.1-1.1 | P1 Awareness: Training matched to each role | missing | competence_training_record |
| ETSI_EN_304_223:5.1.1-2.2 | P1 Awareness: Secure AI coding training for developers | missing | competence_training_record |
| ETSI_EN_304_223:5.1.2-1 | P2 Secure design: Assess need and risk before building | missing | risk_register |
| ETSI_EN_304_223:5.1.2-3 | P2 Secure design: Audit trail of models, data and prompts | missing | etsi_en_304_223.ai_asset_inventory |
| ETSI_EN_304_223:5.1.2-4 | P2 Secure design: Risk assessment of external components | missing | ai_supply_chain_pins |
| ETSI_EN_304_223:5.1.2-7 | P2 Secure design: Due diligence on external providers | missing | vendor_register |
| ETSI_EN_304_223:5.1.3-1 | P3 Threats and risks: Threat modelling and risk management | missing | ai_threat_model |
| ETSI_EN_304_223:5.1.3-1.1 | P3 Threats and risks: Repeat when settings change | missing | ai_threat_model |
| ETSI_EN_304_223:5.1.3-1.3 | P3 Threats and risks: Controls chosen against risk tolerance | missing | risk_register |
| ETSI_EN_304_223:5.1.3-4 | P3 Threats and risks: Ongoing review against risk appetite | missing | risk_register |
| ETSI_EN_304_223:5.1.4-1 | P4 Human responsibility: Human oversight capability | missing | human_oversight_construct |
| ETSI_EN_304_223:5.1.4-3 | P4 Human responsibility: Technical measures behind oversight | missing | human_oversight_construct |
| ETSI_EN_304_223:5.1.4-5 | P4 Human responsibility: End-users told of prohibited uses | missing | deployer_instructions |
| ETSI_EN_304_223:5.2.1-1 | P5 Assets: Asset inventory with dependencies | missing | etsi_en_304_223.ai_asset_inventory |
| ETSI_EN_304_223:5.2.1-2 | P5 Assets: Track, authenticate and version assets | missing | ai_supply_chain_pins |
| ETSI_EN_304_223:5.2.1-3 | P5 Assets: Recovery plans cover AI attacks | missing | continuity_plan |
| ETSI_EN_304_223:5.2.1-3.1 | P5 Assets: Restorable known-good state | missing | restore_test_report |
| ETSI_EN_304_223:5.2.1-4.2 | P5 Assets: Protect confidential data and weights | missing | secret_scanning_config |
| ETSI_EN_304_223:5.2.2-2 | P6 Infrastructure: Controls on externally offered APIs | missing | rate_limiting_config |
| ETSI_EN_304_223:5.2.2-3 | P6 Infrastructure: Separate development and tuning environments | missing | iac_definitions |
| ETSI_EN_304_223:5.2.2-4 | P6 Infrastructure: Published vulnerability disclosure policy | missing | security_policy_file |
| ETSI_EN_304_223:5.2.2-5 | P6 Infrastructure: Tested incident and recovery plans | missing | incident_response_plan |
| ETSI_EN_304_223:5.2.2-6 | P6 Infrastructure: Cloud contracts back these requirements | missing | contract_checklist |
| ETSI_EN_304_223:5.2.3-1 | P7 Supply chain: Secure software supply-chain process | missing | ai_supply_chain_pins |
| ETSI_EN_304_223:5.2.3-2 | P7 Supply chain: Justify weakly documented components | missing | ai_supply_chain_pins |
| ETSI_EN_304_223:5.2.3-3 | P7 Supply chain: Re-run evaluations on released models | missing | evaluation_evidence |
| ETSI_EN_304_223:5.2.4-1 | P8 Documentation: Audit trail of design and maintenance | missing | technical_documentation_dossier |
| ETSI_EN_304_223:5.2.4-1.1 | P8 Documentation: Security-relevant detail in the record | missing | technical_documentation_dossier |
| ETSI_EN_304_223:5.2.4-1.2 | P8 Documentation: Hashes for released model components | missing | ai_supply_chain_pins |
| ETSI_EN_304_223:5.2.4-3 | P8 Documentation: Log of prompt and configuration changes | missing | event_log_evidence |
| ETSI_EN_304_223:5.2.5-1 | P9 Testing: Security assessment before release | missing | ai_red_team_report |
| ETSI_EN_304_223:5.2.5-2 | P9 Testing: Operator testing before deployment | missing | ai_red_team_report |
| ETSI_EN_304_223:5.2.5-2.1 | P9 Testing: Independent security testers | missing | ai_red_team_report |
| ETSI_EN_304_223:5.2.5-4 | P9 Testing: Outputs do not expose model or data | missing | ai_red_team_report |
| ETSI_EN_304_223:5.2.5-4.1 | P9 Testing: Outputs give no unintended control | missing | ai_red_team_report |
| ETSI_EN_304_223:5.3.1-1 | P10 End-user comms: Tell end-users how data is used | missing | privacy_notice |
| ETSI_EN_304_223:5.3.1-2 | P10 End-user comms: Usage and configuration guidance | missing | deployer_instructions |
| ETSI_EN_304_223:5.3.1-2.1 | P10 End-user comms: Guidance on limits and failure modes | missing | model_card |
| ETSI_EN_304_223:5.4.1-1 | P11 Updates: Security updates and patches delivered | missing | update_mechanism_note |
| ETSI_EN_304_223:5.4.1-2 | P11 Updates: Major updates re-tested like new models | missing | ai_red_team_report |
| ETSI_EN_304_223:5.4.2-1 | P12 Monitoring: Log system and user actions | missing | event_log_evidence |
| ETSI_EN_304_223:5.4.2-2 | P12 Monitoring: Analyse logs for anomalies and drift | missing | event_log_evidence |
| ETSI_EN_304_223:5.4.2-4 | P12 Monitoring: Monitor model performance over time | missing | post_market_monitoring_plan |
| ETSI_EN_304_223:5.5.1-1 | P13 Disposal: Dispose of assets on transfer | missing | etsi_en_304_223.end_of_life_note |
| ETSI_EN_304_223:5.5.1-2 | P13 Disposal: Delete data and configuration at retirement | missing | etsi_en_304_223.end_of_life_note |
