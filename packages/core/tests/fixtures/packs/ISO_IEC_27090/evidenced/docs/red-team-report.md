# Red-team report

Reviewed by Example Ltd security.

## Scope

Which system, model version and attack classes (for example prompt injection, jailbreak, adversarial input) were tested?

Ticket ranking model v3 tested for prompt injection and jailbreak.

## Method

Who tested, with which tools and attack sets, and over which dates?

Internal team used an open attack set between 2026-05-04 and 2026-05-08.

## Findings

| Id | Attack class | Result (passed or failed) | Success rate | Severity |
|---|---|---|---|---|
| F-1 | prompt injection | failed | 12% | high |
| F-2 | jailbreak | passed | 0% | low |

## Fixes

Which findings were fixed, which vulnerabilities were accepted, and why?

Two issues were fixed in the input filter; none accepted.

## Retest

Which findings were retested after the fix, and what were the outcomes?

Both findings were retested on 2026-05-20 and passed.
