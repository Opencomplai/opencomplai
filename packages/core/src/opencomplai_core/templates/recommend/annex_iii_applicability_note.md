# Annex III Applicability Note — {{article}}

**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What EU AI Act {{article}} requires

Article 5 lists prohibited AI practices (e.g. subliminal manipulation, social scoring,
real-time remote biometric identification in public spaces with narrow exceptions).
Article 6 (with Annex III) defines which AI systems are classified high-risk, including
biometric identification/categorisation, employment/worker management, and access to
essential services.

## Suggested next step

1. Re-read your system's declared `intended_purpose` in `system-manifest.json` against
   the Annex III categories (employment, education, essential services, law enforcement,
   migration/asylum/border control, administration of justice, biometric identification).
2. If your system's actual behavior includes an Annex III use case not reflected in
   `intended_purpose`, update the manifest to declare it accurately — `opencomplai gaps`
   sources this article from the rule engine (`{{evidence_ref}}`), so an accurate
   declaration is what lets the rule evaluate correctly.
3. If a scan (`opencomplai scan`) flagged evidence (e.g. biometric or scoring code paths)
   not reflected in the declaration, investigate whether the manifest under-declares the
   system's actual purpose before proceeding to a `check` gate.
4. Document your classification reasoning for the Annex IV dossier
   (`opencomplai docs generate`).

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
