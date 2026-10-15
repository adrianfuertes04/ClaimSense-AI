import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
TOOLS_DIR = PROJECT_DIR / "tools"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge-base"
COST_ESTIMATOR_FILE = TOOLS_DIR / "cost-estimator.json"
COVERAGE_TABLE_FILE = TOOLS_DIR / "coverage-table.json"

# LLM Provider Configuration (OpenAI / OpenAI-compatible endpoint)
LLM_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("PORTKEY_API_KEY", "")
LLM_BASE_URL = (
    os.environ.get("OPENAI_BASE_URL")
    or os.environ.get("PORTKEY_BASE_URL")
    or "https://api.openai.com/v1"
).rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")

# Backward compatibility aliases
PORTKEY_API_KEY = LLM_API_KEY
PORTKEY_BASE_URL = LLM_BASE_URL

# Vector Database (Qdrant)
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333").rstrip("/")
QDRANT_COLLECTION = "claims_knowledge_base"
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
