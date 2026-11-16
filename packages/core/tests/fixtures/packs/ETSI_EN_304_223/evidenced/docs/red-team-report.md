# Red-team report

## Scope

Example Ltd ticket-ranker v1.4.0. Attack classes tested: prompt injection, jailbreak and adversarial input.

## Method

Two engineers from the security group used an open attack set and hand-written prompts between 2026-09-21 and 2026-09-25.

## Findings

| Id | Attack class | Result (passed or failed) | Success rate | Severity |
|---|---|---|---|---|
| F-1 | prompt injection | failed | 12 percent | high |
| F-2 | adversarial input | passed | 2 percent | low |

## Fixes

F-1 was fixed with a stricter input filter and a fixed system prompt. F-2 was accepted because the ranking effect is small.

## Retest

F-1 was retested on 2026-10-02 and the success rate fell to 1 percent. The fix held.
