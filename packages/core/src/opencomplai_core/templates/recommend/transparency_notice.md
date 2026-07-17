# Transparency / Disclosure Notice — {{article}}

**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What EU AI Act {{article}} requires

Providers and deployers of certain AI systems (e.g. chatbots, emotion-recognition,
biometric categorisation, deepfake/synthetic-content generators) must ensure natural
persons are informed they are interacting with an AI system, unless this is obvious from
the circumstances (Art. 50).

## Suggested implementation

1. Add a disclosure notice at the point of first interaction, e.g.:

   > "You are interacting with an AI system. [Product name] uses automated processing to
   > generate responses. Contact [support channel] for human assistance."

2. For synthetic or manipulated content (audio/image/video/text), label the content as
   AI-generated or AI-manipulated in a way that is clear and distinguishable, at the
   latest at the time of first interaction or exposure.
3. Store the disclosure copy alongside your manifest so it can be cited in the Annex IV
   dossier (`opencomplai docs generate`).

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
