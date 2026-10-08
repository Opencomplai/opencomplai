"""Art. 50 limited-risk transparency obligations — machine-readable knowledge pack.

Source of truth: eu-ai-act/references/risk-classification.md (Art. 50 section).

Limited-risk systems only require transparency disclosure, not a conformity
assessment. The scanner uses this table to distinguish "Art.50 disclosure"
findings (genuine limited-risk obligations) from "no obligation" (minimal risk).

Applies from 2 August 2026 for new systems; grace period to 2 December 2026
for pre-existing systems on market before that date (for machine-readable marking).

Bundled into core (not the optional opencomplai-ai plugin) alongside the
Annex III and Art. 5 packs so there is one source of truth.
Paragraph and actor are flagged for founder review.
opencomplai_ai.knowledge.limited_risk re-exports these same symbols; edit
only here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LimitedRiskEntry:
    article: str
    trigger_type: str
    title: str
    obligation: str
    keywords: tuple[str, ...]
    code_signals: tuple[str, ...]
    exceptions: tuple[str, ...]
    applies_from: str  # ISO date string
    actor: str  # "provider" or "deployer"
    source: str
    confidence: str
    needs_founder_review: bool


_SOURCE = "Regulation (EU) 2024/1689 Art. 50, paragraph per entry; wording not re-fetched (unverified)"

LIMITED_RISK: list[LimitedRiskEntry] = [
    LimitedRiskEntry(
        article="Art.50(1)",
        trigger_type="chatbot_interaction",
        title="Chatbots and AI interaction systems",
        obligation="Inform users they are interacting with an AI system at first interaction",
        keywords=(
            "chatbot",
            "conversational AI",
            "virtual assistant",
            "AI chat",
            "dialogue system",
            "chatbot interface",
            "AI assistant",
            "chat AI",
            "gemini",
            "regulatory oracle",
        ),
        code_signals=(
            "chatbot",
            "conversational_ai",
            "chat_completion",
            "dialogue_system",
            "virtual_assistant",
            "chat_agent",
            "llm_chat",
            "openai.chat",
            "anthropic.messages",
            "bot_response",
            "generatecontent",
            "generativelanguage.googleapis.com",
            "gemini_api",
        ),
        exceptions=(
            "obvious to a reasonably well-informed user given context",
            "system authorized by law for detection of criminal offenses",
        ),
        applies_from="2026-08-02",
        actor="provider",
        source=_SOURCE,
        confidence="medium",
        needs_founder_review=True,
    ),
    LimitedRiskEntry(
        article="Art.50(2)",
        trigger_type="synthetic_content_marking",
        title="Synthetic audio, image, video or text output - machine-readable marking",
        obligation=(
            "Provider must ensure output is marked in a machine-readable format "
            "and detectable as artificially generated or manipulated"
        ),
        keywords=(
            "synthetic video",
            "synthetic audio",
            "AI-generated image",
            "synthetic media",
            "generative video",
            "text-to-image realistic",
            "neural voice",
            "AI avatar",
        ),
        code_signals=(
            "voice_synthesis",
            "synthetic_voice",
            "tts_realistic",
            "stable_diffusion",
            "midjourney",
            "dall_e",
            "generate_image",
            "video_synthesis",
            "text_to_video",
            "neural_voice",
            "tacotron",
            "wavenet",
        ),
        exceptions=(
            "assistive function for standard editing that does not substantially alter the input",
            "authorised by law for criminal offences",
        ),
        applies_from="2026-08-02",
        actor="provider",
        source=_SOURCE,
        confidence="medium",
        needs_founder_review=True,
    ),
    LimitedRiskEntry(
        article="Art.50(4), first subparagraph",
        trigger_type="synthetic_media_deepfake",
        title="Deepfakes - disclosure by the deployer",
        obligation=(
            "Deployer must disclose that image, audio or video content constituting "
            "a deepfake is artificially generated or manipulated"
        ),
        keywords=("deepfake", "face swap", "voice cloning"),
        code_signals=("deepfake", "face_swap", "voice_clone"),
        exceptions=(
            "authorised by law for criminal offences",
            "evidently artistic, creative, satirical or fictional work: "
            "limited disclosure that does not hamper display",
        ),
        applies_from="2026-08-02",
        actor="deployer",
        source=_SOURCE,
        confidence="medium",
        needs_founder_review=True,
    ),
    LimitedRiskEntry(
        article="Art.50(3)",
        trigger_type="emotion_recognition_categorization_disclosure",
        title="Emotion recognition and biometric categorization systems (disclosure only)",
        obligation=(
            "Inform natural persons exposed to the system of its operation; "
            "comply with GDPR and data protection law"
        ),
        keywords=(
            "emotion recognition disclosure",
            "biometric categorization disclosure",
            "affect detection user",
            "sentiment recognition user-facing",
        ),
        code_signals=(
            "emotion_detect_user",
            "affect_user",
            "biometric_categorize_user",
        ),
        exceptions=("authorized for law enforcement",),
        applies_from="2026-08-02",
        actor="deployer",
        source=_SOURCE,
        confidence="medium",
        needs_founder_review=True,
    ),
    LimitedRiskEntry(
        article="Art.50(4), second subparagraph",
        trigger_type="ai_generated_text_public_interest",
        title="AI-generated text published to inform public on matters of public interest",
        obligation="Disclose content as AI-generated",
        keywords=(
            "AI-generated news",
            "AI journalism",
            "AI public interest content",
            "automated news article",
            "AI-written article",
            "AI text public information",
        ),
        code_signals=(
            "generate_news",
            "automated_journalism",
            "news_generation",
            "article_generate",
            "public_interest_content",
        ),
        exceptions=(
            "authorized for criminal investigation",
            "content with human editorial review and editorial accountability",
        ),
        applies_from="2026-08-02",
        actor="deployer",
        source=_SOURCE,
        confidence="medium",
        needs_founder_review=True,
    ),
]


def match_limited_risk(text: str) -> list[LimitedRiskEntry]:
    text_lower = text.lower()
    return [
        entry
        for entry in LIMITED_RISK
        if any(kw in text_lower for kw in entry.keywords)
        or any(sig in text_lower for sig in entry.code_signals)
    ]
