# Technical documentation outline

<!-- clause: 1 -->
## General description of the product

- Product name, versions and intended purpose: Example Thermostat 2.x, a connected thermostat for homes.
- Hardware, software and firmware components: a controller board, firmware 2.4 and a companion mobile app.

<!-- clause: 2 -->
## Design, development and vulnerability handling

- Design and architecture summary: the controller talks to the cloud over TLS; the app pairs by local code.
- Secure development process followed: reviewed pull requests, static analysis and dependency scanning on every build.
- How vulnerabilities are handled and patches issued: see docs/vulnerability-handling.md; patches ship as signed firmware.

<!-- clause: 3 -->
## Cybersecurity risk assessment

- Threats and risks considered: network eavesdropping, forged firmware, stolen pairing codes.
- Controls and measures chosen, with likelihood and severity: TLS, signed updates and rate-limited pairing; residual risk low.

<!-- clause: 4 -->
## Basis for the support period

- Support period length and expected use time: 5 years, matching the expected use time of about five years.
- End of support date: 2031-03-01

<!-- clause: 5 -->
## Standards and solutions applied

- Standards and specifications applied: none formally harmonised yet; the team follows common secure-by-design practice.
- Other solutions used where no standard was followed: an internal secure coding checklist.

<!-- clause: 6 -->
## Test reports

- Test reports and their results: unit and integration test reports kept per release, all passing.
- Penetration testing findings and fixes: one external test in 2026; two low findings fixed in 2.3.

<!-- clause: 7 -->
## Copy of the declaration of conformity

- Declaration copy, date and signer role: draft held in the release folder, dated 2026-02-20, signed by the managing director.

<!-- clause: 8 -->
## Software bill of materials

- SBOM format and where it is kept: CycloneDX JSON in sbom.json.
- Components and dependencies listed: all firmware and app dependencies with versions.
