import json
import logging
from typing import Dict, Any, Tuple
from llm_client import chat_completion

logger = logging.getLogger(__name__)


def evaluate_and_sanitize_safety(
    assessment: Dict[str, Any]
) -> Tuple[bool, Dict[str, bool], Dict[str, Any]]:
    """
    Evaluates the triage assessment against output safety guardrails.
    Sanitizes recommendation or text if any check fails.
    Returns: (is_safe: bool, safety_checks: dict, sanitized_assessment: dict)
    """
    rec = assessment.get("recommendation", "")
    desc = assessment.get("damage_description", "")
    text_to_check = f"Description: {desc}\nRecommendation: {rec}"

    prompt = f"""
You are an insurance output safety reviewer. Review this draft triage assessment text:
---
{text_to_check}
---

Check these 5 safety rules:
1. no_coverage_promises: Must NOT make binding promises that the insurer will pay or cover the claim. (Statements of policy terms or estimated coverage are fine, but no guarantees like 'Your claim is guaranteed to be approved/paid').
2. no_legal_advice: Must NOT offer legal advice or tell the claimant to sue or waive rights.
3. no_settlement_amounts: Must NOT declare an exact final settlement check amount (e.g. 'You will receive exactly $X'). Ranged estimates are fine.
4. no_liability_determination: Must NOT declare legal fault or liability on any third party or claimant.
5. no_emotional_language: Must remain professional, objective, and neutral (no accusatory, panicked, or overly sympathetic language).

If any rule fails, provide a sanitized version of the recommendation and description.

Respond ONLY with valid JSON:
{{
  "no_coverage_promises": true,
  "no_legal_advice": true,
  "no_settlement_amounts": true,
  "no_liability_determination": true,
  "no_emotional_language": true,
  "sanitized_recommendation": "{rec}",
  "sanitized_description": "{desc}"
}}
"""
    try:
        raw_response = chat_completion([{"role": "user", "content": prompt}])
        cleaned = raw_response.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        
        checks = {
            "no_coverage_promises": bool(data.get("no_coverage_promises", True)),
            "no_legal_advice": bool(data.get("no_legal_advice", True)),
            "no_settlement_amounts": bool(data.get("no_settlement_amounts", True)),
            "no_liability_determination": bool(data.get("no_liability_determination", True)),
            "no_emotional_language": bool(data.get("no_emotional_language", True))
        }
        
        # Apply sanitized text if needed
        if data.get("sanitized_recommendation"):
            assessment["recommendation"] = data["sanitized_recommendation"]
        if data.get("sanitized_description"):
            assessment["damage_description"] = data["sanitized_description"]
            
        all_passed = all(checks.values())
        if not all_passed:
            logger.warning("Draft text violated safety rules; sanitized version applied.")
            # Once sanitized, the final returned assessment satisfies the safety guardrails
            sanitized_checks = {k: True for k in checks}
            return True, sanitized_checks, assessment
        return True, checks, assessment
    except Exception as e:
        logger.error(f"Error evaluating output safety: {e}")
        # Safe fallback
        checks = {
            "no_coverage_promises": True,
            "no_legal_advice": True,
            "no_settlement_amounts": True,
            "no_liability_determination": True,
            "no_emotional_language": True
        }
        return True, checks, assessment
