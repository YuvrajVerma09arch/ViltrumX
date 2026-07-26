"""
LLM explanation adapter (Week 4 — ARCHITECTURE §8).

Two backends: Groq (default, free tier) and Ollama (sovereign mode).
The LLM only ever describes verified facts — it never scores, decides, or
triggers actions. Grounding rule: the prompt contains only the attack chain
and provenance entries we hand it.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a security analyst writing a concise incident narrative. "
    "Use only the facts provided. Do not speculate. "
    "Write in plain language a non-technical founder can understand. "
    "Keep the technical section under 120 words and the founder section under 80 words."
)


def _groq_client():
    from langchain_groq import ChatGroq

    return ChatGroq(api_key=settings.GROQ_API_KEY, model="llama3-8b-8192", temperature=0.2)


def _ollama_client():
    from langchain_ollama import ChatOllama

    return ChatOllama(base_url=settings.OLLAMA_BASE_URL, model="llama3.1:8b", temperature=0.2)


def _get_client(tenant=None):
    provider = getattr(tenant, "llm_provider", None) or settings.LLM_PROVIDER
    if provider == "ollama":
        return _ollama_client()
    return _groq_client()


def generate_narrative(tenant, incident, attack_chain, provenance_steps) -> dict:
    """
    Generate EN narrative grounded on the incident facts.
    Returns the same shape as demo_narratives.NARRATIVE["en"].
    """
    chain_text = "\n".join(
        f"- {s.time_label} {s.title}: {s.detail} [{s.mitre}]" for s in attack_chain
    )
    prov_text = "\n".join(f"- {p.step}: {p.detail}" for p in provenance_steps[:6])

    prompt = f"""Incident: {incident.external_id} — {incident.title}
Entity: {incident.entity}
Severity: {incident.severity}

Attack chain:
{chain_text}

Actions taken:
{prov_text}

Write:
1. TECHNICAL (≤120 words): what happened, how it was detected, what was done.
2. FOUNDER (≤80 words): plain language for a non-technical CEO.
3. DECISION: one sentence asking the founder to approve or reject the pending L4 action.
"""
    try:
        client = _get_client(tenant)
        response = client.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        text = response.content
        technical, founder, decision = _parse_response(text, incident)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM generation failed, using fixture: %s", exc)
        from reports.demo_narratives import NARRATIVE

        return NARRATIVE["en"]

    return {
        "technical": technical,
        "founder": founder,
        "impact": _impact_rows(incident),
        "decision": decision,
    }


def _parse_response(text: str, incident) -> tuple[str, str, str]:
    lines = text.strip().split("\n")
    sections = {"technical": [], "founder": [], "decision": []}
    current = None
    for line in lines:
        low = line.lower()
        if "technical" in low and ":" in low:
            current = "technical"
        elif "founder" in low and ":" in low:
            current = "founder"
        elif "decision" in low and ":" in low:
            current = "decision"
        elif current:
            sections[current].append(line.strip())
    technical = " ".join(sections["technical"]).strip() or text[:400]
    founder = " ".join(sections["founder"]).strip() or text[400:700]
    decision = " ".join(sections["decision"]).strip() or (
        f"Approve the proposed action on {incident.entity}?"
    )
    return technical, founder, decision


def _impact_rows(incident) -> list:
    from reports.demo_narratives import NARRATIVE

    return NARRATIVE["en"]["impact"]
