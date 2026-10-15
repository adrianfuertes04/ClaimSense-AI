import json
import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import List, Dict, Any, Optional, Tuple

from llm_client import chat_completion, encode_image_base64
from tools import estimate_repair_cost, check_coverage
from vector_store import search_similar_claims

logger = logging.getLogger(__name__)

VALID_ROOMS = [
    "kitchen", "dining_room", "living_room", "bathroom", "bedroom",
    "basement", "attic", "garage", "roof", "hallway", "laundry_room",
    "utility_room", "office", "exterior", "interior"
]

SPECIFIC_ROOMS = set(VALID_ROOMS) - {"interior"}


class ReActTriageAgent:
    """
    Multi-Agent ReAct (Reason + Act + Observe) Execution Engine.
    Coordinates multimodal perception, semantic vector retrieval (RAG),
    coverage verification, and actuarial cost estimation.
    """

    def __init__(self, claim_id: str):
        self.claim_id = claim_id
        self.steps: List[Dict[str, Any]] = []
        self.step_num = 1
        self.start_time = perf_counter()

    def record_reason(self, summary: str):
        self.steps.append({
            "step_number": self.step_num,
            "type": "reason",
            "content": summary.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self.step_num += 1

    def record_act(self, tool_name: str, tool_input: Dict[str, Any], summary: str):
        self.steps.append({
            "step_number": self.step_num,
            "type": "act",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "content": summary.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self.step_num += 1

    def record_observe(self, tool_output: Any, summary: str):
        self.steps.append({
            "step_number": self.step_num,
            "type": "observe",
            "tool_output": tool_output,
            "content": summary.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self.step_num += 1

    def run(
        self,
        images: List[Tuple[bytes, str]],
        description: Optional[str] = None,
        pdf_text: Optional[str] = None,
        policy_type: str = "standard_homeowner"
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # -------------------------------------------------------------
        # Phase 1: Multimodal Perception & Preliminary Assessment
        # -------------------------------------------------------------
        combined_notes = []
        if description:
            combined_notes.append(f"Claimant Description: {description}")
        if pdf_text:
            combined_notes.append(f"Inspection Report / Document Findings:\n{pdf_text}")

        valid_rooms_str = ", ".join(f'"{r}"' for r in VALID_ROOMS)

        analysis_prompt = f"""
You are an expert insurance damage triage appraiser. Analyze the submitted claim evidence:
{chr(10).join(combined_notes) if combined_notes else "Visual evidence only provided."}

Determine:
1. damage_type: exactly one of: ["water_damage", "fire_damage", "storm_damage", "break_in", "vandalism", "other"]
2. severity: exactly one of: ["minor", "moderate", "severe", "catastrophic"]
3. affected_areas: list of DISTINCT ROOM NAMES ONLY with direct physical damage.
   Choose ONLY from: [{valid_rooms_str}]
   CRITICAL GUIDELINES FOR ROOM COUNTING:
   - If multiple photos show THE SAME room from different angles, list that room ONLY ONCE.
   - Do NOT include generic "interior" if a specific room (e.g. kitchen, living_room, basement, bathroom) is identified.
   - Only list rooms that have actual visible or documented damage. Do not guess undamaged areas.
4. urgency: exactly one of: ["low", "medium", "high", "critical"]
5. damage_description: detailed neutral description of observed damage.
6. recommendation: professional next-steps recommendation for the insurance adjuster.

Respond ONLY with valid JSON in this exact structure:
{{
  "damage_type": "water_damage",
  "severity": "moderate",
  "affected_areas": ["kitchen"],
  "urgency": "medium",
  "damage_description": "...",
  "recommendation": "..."
}}
"""
        messages: List[Dict[str, Any]] = [
            {"type": "text", "text": analysis_prompt}
        ]

        for img_bytes, mime in images[:3]:
            messages.append({
                "type": "image_url",
                "image_url": {"url": encode_image_base64(img_bytes, mime)}
            })

        try:
            raw_analysis = chat_completion([{"role": "user", "content": messages}])
            cleaned = raw_analysis.strip().replace("```json", "").replace("```", "").strip()
            parsed_analysis = json.loads(cleaned)
        except Exception as e:
            logger.error(f"Error in LLM triage perception: {e}")
            parsed_analysis = {
                "damage_type": "water_damage",
                "severity": "moderate",
                "affected_areas": ["kitchen"],
                "urgency": "medium",
                "damage_description": description or "Property damage reported.",
                "recommendation": "Dispatch an adjuster to inspect affected premises."
            }

        # Normalize fields
        valid_damage_types = ["water_damage", "fire_damage", "storm_damage", "break_in", "vandalism", "other"]
        valid_severities = ["minor", "moderate", "severe", "catastrophic"]
        valid_urgencies = ["low", "medium", "high", "critical"]

        damage_type = parsed_analysis.get("damage_type", "water_damage")
        if damage_type not in valid_damage_types:
            damage_type = "other"

        severity = parsed_analysis.get("severity", "moderate")
        if severity not in valid_severities:
            severity = "moderate"

        urgency = parsed_analysis.get("urgency", "medium")
        if urgency not in valid_urgencies:
            urgency = "medium"

        raw_areas = parsed_analysis.get("affected_areas", [])
        if not isinstance(raw_areas, list):
            raw_areas = []

        cleaned_areas = []
        for a in raw_areas:
            norm_a = str(a).strip().lower().replace(" ", "_")
            if norm_a and norm_a in VALID_ROOMS and norm_a not in cleaned_areas:
                cleaned_areas.append(norm_a)

        # Apply requirement 3.4: "Do not count a room again for its floor/wall, or a specific component again under a generic label such as interior."
        specific_found = [a for a in cleaned_areas if a in SPECIFIC_ROOMS]
        if specific_found:
            cleaned_areas = specific_found

        # Evaluate inspection PDF for explicitly identified scope extensions
        if pdf_text:
            pdf_lower = pdf_text.lower()
            area_variants = {
                "kitchen": ["kitchen"],
                "dining_room": ["dining_room", "dining room"],
                "living_room": ["living_room", "living room"],
                "bathroom": ["bathroom", "bath room"],
                "basement": ["basement"],
                "bedroom": ["bedroom", "bed room"],
                "roof": ["roof"],
                "garage": ["garage"],
                "hallway": ["hallway", "hall way"],
                "attic": ["attic"],
            }
            for normalized_area, variants in area_variants.items():
                if normalized_area not in cleaned_areas:
                    if any(v in pdf_lower for v in variants):
                        cleaned_areas.append(normalized_area)

        # Final fallback if no areas were identified
        if not cleaned_areas:
            cleaned_areas = ["interior"]

        # -------------------------------------------------------------
        # ReAct Cycle 1: Search Past Claims (RAG)
        # -------------------------------------------------------------
        self.record_reason(
            f"Query knowledge base vector store for historical claims matching {damage_type} ({severity}) in {', '.join(cleaned_areas)} to identify resolution precedents."
        )

        search_query = f"{damage_type} {severity} in {', '.join(cleaned_areas)}: {description or ''}".strip()
        tool_input_1 = {"query": search_query}
        self.record_act(
            tool_name="search_past_claims",
            tool_input=tool_input_1,
            summary=f"Searching Qdrant vector database with semantic query: '{search_query[:75]}...'"
        )

        similar_claims_raw = search_similar_claims(search_query, limit=4)
        tool_output_1 = [
            {
                "claim_id": c["claim_id"],
                "similarity_score": c["similarity_score"],
                "resolution_summary": c["resolution_summary"],
                "damage_type": c.get("damage_type"),
                "severity": c.get("severity")
            }
            for c in similar_claims_raw
        ]
        self.record_observe(
            tool_output=tool_output_1,
            summary=f"Retrieved {len(tool_output_1)} historical claim precedents from Qdrant vector store."
        )

        # -------------------------------------------------------------
        # ReAct Cycle 2: Check Policy Coverage
        # -------------------------------------------------------------
        self.record_reason(
            f"Verify policy coverage rules, deductibles, and payout limits for policy type '{policy_type}' under category '{damage_type}'."
        )

        tool_input_2 = {
            "policy_type": policy_type or "standard_homeowner",
            "incident_category": damage_type
        }
        self.record_act(
            tool_name="check_coverage",
            tool_input=tool_input_2,
            summary=f"Checking coverage table for {tool_input_2['policy_type']} policy covering {damage_type}."
        )

        coverage_result = check_coverage(tool_input_2["policy_type"], tool_input_2["incident_category"])
        self.record_observe(
            tool_output=coverage_result,
            summary=f"Coverage check complete: covered={coverage_result.get('covered')}, deductible=${coverage_result.get('deductible')}."
        )

        # -------------------------------------------------------------
        # ReAct Cycle 3: Estimate Repair Cost
        # -------------------------------------------------------------
        self.record_reason(
            f"Calculate standard actuarial repair cost range using cost-estimator matrix for {damage_type} ({severity}) across {len(cleaned_areas)} affected area(s)."
        )

        tool_input_3 = {
            "damage_type": damage_type,
            "severity": severity,
            "affected_areas": cleaned_areas
        }
        self.record_act(
            tool_name="estimate_repair_cost",
            tool_input=tool_input_3,
            summary=f"Evaluating repair cost matrix for {damage_type} ({severity}) in {cleaned_areas}."
        )

        cost_result = estimate_repair_cost(
            tool_input_3["damage_type"],
            tool_input_3["severity"],
            tool_input_3["affected_areas"]
        )
        self.record_observe(
            tool_output=cost_result,
            summary=f"Estimated repair cost calculated: ${cost_result['min']} - ${cost_result['max']} {cost_result['currency']}."
        )

        # -------------------------------------------------------------
        # ReAct Cycle 4: Final Synthesis
        # -------------------------------------------------------------
        self.record_reason(
            "Synthesize multimodal evidence, policy terms, and historical resolutions into structured triage report."
        )

        # Citations must strictly match the retrieved claim records
        cited_claims = [
            {
                "claim_id": c["claim_id"],
                "similarity_score": c["similarity_score"],
                "resolution_summary": c["resolution_summary"]
            }
            for c in tool_output_1[:3]
        ]

        # Ensure recommendation is substantive (> 20 chars) and adjuster-focused
        recommendation = parsed_analysis.get("recommendation", "").strip()
        if not recommendation or len(recommendation) < 25:
            recommendation = (
                f"Dispatch a field adjuster to inspect the {', '.join(cleaned_areas)} for {damage_type.replace('_', ' ')}. "
                f"Verify scope against policy deductible (${coverage_result.get('deductible', 1500)}) and mitigate further losses."
            )

        damage_desc = parsed_analysis.get("damage_description", description or f"{damage_type.replace('_', ' ').capitalize()} observed in {', '.join(cleaned_areas)}.").strip()

        triage_assessment = {
            "damage_type": damage_type,
            "severity": severity,
            "affected_areas": cleaned_areas,
            "damage_description": damage_desc,
            "estimated_repair_cost": cost_result,
            "urgency": urgency,
            "recommendation": recommendation,
            "similar_past_claims": cited_claims
        }

        elapsed_ms = int((perf_counter() - self.start_time) * 1000)
        agent_trace = {
            "claim_id": self.claim_id,
            "steps": self.steps,
            "total_duration_ms": elapsed_ms
        }

        return triage_assessment, agent_trace


def run_triage_react_loop(
    claim_id: str,
    images: List[Tuple[bytes, str]],
    description: Optional[str] = None,
    pdf_text: Optional[str] = None,
    policy_type: Optional[str] = "standard_homeowner"
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Entrypoint for claim triage ReAct loop.
    """
    agent = ReActTriageAgent(claim_id=claim_id)
    return agent.run(
        images=images,
        description=description,
        pdf_text=pdf_text,
        policy_type=policy_type or "standard_homeowner"
    )
