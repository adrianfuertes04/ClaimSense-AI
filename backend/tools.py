import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from config import COST_ESTIMATOR_FILE, COVERAGE_TABLE_FILE

logger = logging.getLogger(__name__)

# Cached tables
_cost_table = None
_coverage_table = None


def get_cost_table() -> Dict[str, Any]:
    global _cost_table
    if _cost_table is None:
        if COST_ESTIMATOR_FILE.is_file():
            _cost_table = json.loads(COST_ESTIMATOR_FILE.read_text(encoding="utf-8-sig"))
        else:
            raise FileNotFoundError(f"Cost estimator table missing: {COST_ESTIMATOR_FILE}")
    return _cost_table


def get_coverage_table() -> Dict[str, Any]:
    global _coverage_table
    if _coverage_table is None:
        if COVERAGE_TABLE_FILE.is_file():
            _coverage_table = json.loads(COVERAGE_TABLE_FILE.read_text(encoding="utf-8-sig"))
        else:
            raise FileNotFoundError(f"Coverage table missing: {COVERAGE_TABLE_FILE}")
    return _coverage_table


def estimate_repair_cost(
    damage_type: str,
    severity: str,
    affected_areas: List[str]
) -> Dict[str, Any]:
    """
    Estimates the repair cost based on the cost-estimator lookup table.
    Multiplies min_per_area and max_per_area by the count of distinct affected areas.
    """
    table = get_cost_table()
    matrix = table.get("cost_matrix", {})
    
    # Normalize inputs
    norm_damage_type = (damage_type or "other").strip().lower()
    norm_severity = (severity or "moderate").strip().lower()
    
    if norm_damage_type not in matrix:
        norm_damage_type = "other"
    if norm_severity not in matrix[norm_damage_type]:
        norm_severity = "moderate"
        
    row = matrix[norm_damage_type][norm_severity]
    
    # Count distinct affected areas
    cleaned_areas = [str(a).strip().lower() for a in affected_areas if str(a).strip()]
    count = max(1, len(set(cleaned_areas)))
    
    min_cost = row["min_per_area"] * count
    max_cost = row["max_per_area"] * count
    
    return {
        "min": min_cost,
        "max": max_cost,
        "currency": "USD"
    }


def check_coverage(
    policy_type: str,
    incident_category: str
) -> Dict[str, Any]:
    """
    Checks policy coverage using the coverage-table lookup table.
    """
    table = get_coverage_table()
    policies = table.get("policies", {})
    
    norm_policy = (policy_type or "standard_homeowner").strip().lower()
    norm_category = (incident_category or "other").strip().lower()
    
    policy = policies.get(norm_policy, policies.get("standard_homeowner", {}))
    covered_categories = policy.get("covered_categories", [])
    
    is_covered = norm_category in covered_categories
    
    return {
        "covered": is_covered,
        "deductible": policy.get("deductible", 1500),
        "max_payout": policy.get("max_payout", 250000),
        "notes": policy.get("notes", "")
    }
