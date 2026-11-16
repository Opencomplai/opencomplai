## Opencomplai Compliance Scan

| Field | Value |
|-------|-------|
| Result | `control_fail` |
| System | `example-ltd-cra` |
| Commit | `unresolved` |
| Signed | `no (unsigned artifact)` |
| Failed controls | `CRA: 49 requirement(s)` |

### Cyber Resilience Act Regulation (EU) 2024/2847 (evaluated, not an audit, certification or legal assessment)

| Requirement | Title | Status | Evidence |
|-------------|-------|--------|----------|
| CRA:Art. 13(2) | Cybersecurity risk assessment | missing | ai_threat_model |
| CRA:Art. 13(3) | Documented, updated risk assessment | missing | cra.technical_documentation#3 |
| CRA:Art. 13(5) | Due diligence on third-party components | missing | sbom_file |
| CRA:Art. 13(6) | Component flaws reported upstream and fixed | missing | vulnerability_handling_policy |
| CRA:Art. 13(7) | Systematic cybersecurity documentation | missing | cra.technical_documentation#2 |
| CRA:Art. 13(8) | Support period and vulnerability handling | missing | cra.support_period_statement |
| CRA:Art. 13(9) | Security updates kept available | missing | update_mechanism_note |
| CRA:Art. 13(17) | Single point of contact | missing | security_policy_file |
| CRA:Art. 13(18) | User information and instructions supplied | missing | cra.user_information#8 |
| CRA:Art. 13(19) | Support period end date stated | missing | cra.support_period_statement |
| CRA:Art. 14(1) | Actively exploited vulnerability reporting | missing | cra.vulnerability_notification_record#early-warning |
| CRA:Art. 14(3) | Severe incident reporting | missing | cra.vulnerability_notification_record#notification |
| CRA:Art. 14(8) | Users informed of exploited flaws and incidents | missing | cra.vulnerability_notification_record#user-information |
| CRA:Annex I Part I (1) | Risk-based level of cybersecurity by design | missing | ai_threat_model |
| CRA:Annex I Part I (2)(a) | No known exploitable vulnerabilities at release | missing | sast_config |
| CRA:Annex I Part I (2)(b) | Secure by default configuration | missing | secure_defaults_config |
| CRA:Annex I Part I (2)(c) | Vulnerabilities fixable by security updates | missing | update_mechanism_note |
| CRA:Annex I Part I (2)(d) | Protection from unauthorised access | missing | policy_access_control |
| CRA:Annex I Part I (2)(e) | Confidentiality of data | missing | policy_cryptography |
| CRA:Annex I Part I (2)(f) | Integrity of data, commands and programs | missing | signed_release_config |
| CRA:Annex I Part I (2)(h) | Availability of essential functions | missing | rate_limiting_config |
| CRA:Annex I Part I (2)(j) | Limited attack surface | missing | iac_definitions |
| CRA:Annex I Part I (2)(k) | Exploitation mitigation | missing | sast_config |
| CRA:Annex I Part I (2)(l) | Security logging and monitoring | missing | event_log_evidence |
| CRA:Annex I Part II (1) | Vulnerabilities and components documented, SBOM | missing | ai_supply_chain_pins |
| CRA:Annex I Part II (2) | Vulnerabilities remediated without delay | missing | vulnerability_handling_policy |
| CRA:Annex I Part II (3) | Regular security tests and reviews | missing | ci_test_workflow |
| CRA:Annex I Part II (4) | Public disclosure of fixed vulnerabilities | missing | vulnerability_handling_policy |
| CRA:Annex I Part II (5) | Coordinated vulnerability disclosure policy | missing | vulnerability_handling_policy |
| CRA:Annex I Part II (6) | Vulnerability information sharing and contact | missing | security_policy_file |
| CRA:Annex I Part II (7) | Secure distribution of updates | missing | signed_release_config |
| CRA:Annex I Part II (8) | Updates disseminated without delay | missing | update_mechanism_note |
| CRA:Annex II (1) | Manufacturer identity and contact | missing | cra.user_information#1 |
| CRA:Annex II (2) | Vulnerability reporting contact | missing | cra.user_information#2 |
| CRA:Annex II (3) | Product identification | missing | cra.user_information#3 |
| CRA:Annex II (4) | Intended purpose and security properties | missing | cra.user_information#4 |
| CRA:Annex II (5) | Known risk circumstances and foreseeable misuse | missing | cra.user_information#5 |
| CRA:Annex II (6) | Web address of declaration of conformity | missing | cra.user_information#6 |
| CRA:Annex II (7) | Security support offered and end date | missing | cra.user_information#7 |
| CRA:Annex II (8) | Instructions for secure use through to decommissioning | missing | cra.user_information#8 |
| CRA:Annex II (9) | Location of the SBOM if offered | missing | cra.user_information#9 |
| CRA:Annex VII (1) | General description of the product | missing | cra.technical_documentation#1 |
| CRA:Annex VII (2) | Design, development, production, vulnerability handling | missing | cra.technical_documentation#2 |
| CRA:Annex VII (3) | Cybersecurity risk assessment in the file | missing | cra.technical_documentation#3 |
| CRA:Annex VII (4) | Basis for the support period | missing | cra.technical_documentation#4 |
| CRA:Annex VII (5) | Standards and solutions applied | missing | cra.technical_documentation#5 |
| CRA:Annex VII (6) | Test reports | missing | cra.technical_documentation#6 |
| CRA:Annex VII (7) | Copy of the declaration of conformity | missing | cra.technical_documentation#7 |
| CRA:Annex VII (8) | SBOM available on authority request | missing | cra.technical_documentation#8 |
