"""
Five demo AI system manifest definitions (prefixed demo-).

Each dict is a valid SystemManifest payload accepted by
POST /v1/manifests/validate and POST /v1/risk/classify.
"""

from __future__ import annotations

DEMO_SYSTEMS: list[dict] = [
    {
        "system_id": "demo-credit-scoring-v1",
        "name": "Credit Risk Scorer",
        "version": "1.3.0",
        "risk_class": "HIGH",
        "annex_iii_category": "Art. 6 + Annex III §5b",
        "description": (
            "Automated creditworthiness scoring used in consumer loan decisions. "
            "Passed all controls; slight bias-alert trend detected mid-period."
        ),
        "owner": "demo-tenant",
        "tags": ["finance", "credit", "high-risk"],
        "policy_bundle_version": "v2.1.0",
    },
    {
        "system_id": "demo-hr-hiring-v2",
        "name": "HR Candidate Ranker",
        "version": "2.0.1",
        "risk_class": "HIGH",
        "annex_iii_category": "Annex III §4a",
        "description": (
            "Ranks job applicants using structured interview signals. "
            "Was halted for HITL review; resumed after remediation."
        ),
        "owner": "demo-tenant",
        "tags": ["hr", "hiring", "high-risk"],
        "policy_bundle_version": "v2.1.0",
    },
    {
        "system_id": "demo-medical-triage-v1",
        "name": "Medical Triage Assistant",
        "version": "1.1.0",
        "risk_class": "HIGH",
        "annex_iii_category": "Annex III §1a",
        "description": (
            "Emergency-department triage support system. "
            "All scan results PASS but policy bundle is frozen at v1.0.0 — triggers drift alert."
        ),
        "owner": "demo-tenant",
        "tags": ["healthcare", "triage", "high-risk"],
        "policy_bundle_version": "v1.0.0",  # intentionally stale
    },
    {
        "system_id": "demo-customer-chat-v1",
        "name": "Customer Service Bot",
        "version": "3.2.0",
        "risk_class": "LIMITED",
        "annex_iii_category": "Art. 50 transparency",
        "description": (
            "AI-powered customer support assistant. "
            "Steady green; low risk; no failed controls across the entire period."
        ),
        "owner": "demo-tenant",
        "tags": ["customer-service", "limited-risk"],
        "policy_bundle_version": "v2.1.0",
    },
    {
        "system_id": "demo-inventory-opt-v1",
        "name": "Inventory Optimizer",
        "version": "1.0.4",
        "risk_class": "MINIMAL",
        "annex_iii_category": "Not listed (MINIMAL)",
        "description": (
            "Supply-chain inventory forecasting model. "
            "All PASS, minimal documentation required, very high control pass rate."
        ),
        "owner": "demo-tenant",
        "tags": ["supply-chain", "minimal-risk"],
        "policy_bundle_version": "v2.1.0",
    },
]

HIGH_RISK_SYSTEM_IDS = {
    s["system_id"] for s in DEMO_SYSTEMS if s["risk_class"] == "HIGH"
}
