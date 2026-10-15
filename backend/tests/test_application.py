import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import pytest
from fastapi.testclient import TestClient

from main import app
from tools import estimate_repair_cost, check_coverage

client = TestClient(app)



def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data
    assert "vector_db" in data["services"]
    assert "llm" in data["services"]


def test_tool_estimate_repair_cost():
    result = estimate_repair_cost("water_damage", "moderate", ["kitchen", "dining_room"])
    assert result["currency"] == "USD"
    # In cost-estimator.json, water_damage moderate is 2000 to 8000 per area
    # For 2 areas, min is 4000 and max is 16000
    assert result["min"] == 4000
    assert result["max"] == 16000


def test_tool_check_coverage():
    result = check_coverage("standard_homeowner", "water_damage")
    assert result["covered"] is True
    assert result["deductible"] == 1500
    assert result["max_payout"] == 250000

    basic_result = check_coverage("basic_homeowner", "water_damage")
    assert basic_result["covered"] is False


def test_empty_triage_submission_rejected():
    response = client.post("/api/v1/claims/triage")
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "intake_validation" in data
    assert data["intake_validation"]["is_property_damage"] is False


def test_tool_estimate_repair_cost_deduplication():
    # Duplicate areas should be deduplicated (1 distinct room)
    result = estimate_repair_cost("water_damage", "moderate", ["kitchen", "kitchen", "KITCHEN", ""])
    assert result["min"] == 2000
    assert result["max"] == 8000


def test_tool_estimate_repair_cost_unknown_fallback():
    # Unknown damage type and severity should fall back safely without raising exception
    result = estimate_repair_cost("unknown_type", "unknown_severity", ["kitchen"])
    assert result["currency"] == "USD"
    assert result["min"] > 0
    assert result["max"] >= result["min"]


def test_tool_check_coverage_unknown_policy_fallback():
    # Unknown policy type falls back to standard_homeowner
    result = check_coverage("mysterious_policy", "water_damage")
    assert "covered" in result
    assert result["deductible"] == 1500

