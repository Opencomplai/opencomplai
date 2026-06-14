---
name: Vulnerability Triage
about: Track a dependency or code vulnerability through triage and remediation
title: "[VULN] <package> <CVE-ID or advisory>"
labels: security, vulnerability
assignees: ''
---

## Summary

**CVE / Advisory ID:**
**Package:** (e.g., `requests`, `lodash`)
**Affected version(s):**
**Fixed version (if available):**
**CVSS Score:** (base score)
**Detected by:** [ ] pip-audit  [ ] npm audit  [ ] Dependabot  [ ] Manual  [ ] External report

---

## Scope Assessment

**Component(s) affected in Opencomplai:**

**Is the vulnerable code path reachable in production?**
[ ] Yes — explain:
[ ] No — explain:
[ ] Unknown

**Contextual severity:** [ ] Critical  [ ] High  [ ] Medium  [ ] Low

---

## Remediation Plan

**Target fix date** (per [Vulnerability Management SLA](../../SECURITY.md)):

**Proposed fix:**
[ ] Upgrade to version ___
[ ] Apply patch ___
[ ] Compensating control ___
[ ] Accept risk (requires Security Lead sign-off — document in Risk Register)

---

## Verification

- [ ] Fix applied and merged
- [ ] CI scanner no longer flags this CVE
- [ ] Risk Register updated (if deferred/accepted)

---

## References

- Advisory link:
- Related PR/commit:
