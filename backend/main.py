import io
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pypdf import PdfReader

from config import PORTKEY_API_KEY, PORTKEY_BASE_URL, LLM_MODEL
from llm_client import is_llm_configured
from vector_store import is_qdrant_connected, init_knowledge_base
from agents.intake import validate_intake
from agents.triage import run_triage_react_loop
from agents.safety import evaluate_and_sanitize_safety


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# In-memory storage for triage reports and traces
claims_db = {}
traces_db = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Claim Triage API...")
    try:
        init_knowledge_base()
    except Exception as exc:
        logger.warning(f"Initial knowledge base setup deferred or failed: {exc}")
    yield
    logger.info("Shutting down Claim Triage API.")


app = FastAPI(
    title="Claim Triage API",
    description="AI-powered property damage claim triage system",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health_check():
    vector_ok = is_qdrant_connected()
    llm_ok = is_llm_configured()
    
    return {
        "status": "healthy",
        "services": {
            "vector_db": "connected" if vector_ok else "disconnected",
            "llm": "configured" if llm_ok else "not_configured"
        }
    }


@app.post("/api/v1/claims/triage", status_code=status.HTTP_200_OK)
async def triage_claim(
    image: Optional[UploadFile] = File(None),
    images: Optional[List[UploadFile]] = File(None),
    description: Optional[str] = Form(None),
    document: Optional[UploadFile] = File(None),
    policy_type: Optional[str] = Form("standard_homeowner")
):
    # Collect all image files
    all_image_files: List[UploadFile] = []
    if image is not None:
        all_image_files.append(image)
    if images:
        all_image_files.extend(images)
        
    has_images = bool(all_image_files)
    has_desc = bool(description and description.strip())
    
    if not has_images and not has_desc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Missing input",
                "message": "At least one damage photo or a non-empty description is required.",
                "intake_validation": {
                    "is_property_damage": False,
                    "is_valid_image": None,
                    "no_pii_detected": True,
                    "no_offensive_content": True
                }
            }
        )

    # Read image bytes
    loaded_images = []
    for img_file in all_image_files:
        content = await img_file.read()
        mime = img_file.content_type or ("image/png" if img_file.filename and img_file.filename.lower().endswith(".png") else "image/jpeg")
        loaded_images.append((content, mime))

    # Read PDF text if document is provided
    pdf_text = None
    if document is not None:
        try:
            doc_bytes = await document.read()
            reader = PdfReader(io.BytesIO(doc_bytes))
            pages_text = [page.extract_text() for page in reader.pages if page.extract_text()]
            pdf_text = "\n".join(pages_text)
            logger.info(f"Extracted {len(pdf_text)} characters from uploaded PDF: {document.filename}")
        except Exception as exc:
            logger.warning(f"Failed to extract text from PDF: {exc}")

    # 1. Intake Validation
    is_valid, intake_val, reason = validate_intake(loaded_images, description)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Intake validation failed",
                "message": reason or "The submitted evidence failed intake validation checks.",
                "intake_validation": intake_val
            }
        )

    # Generate claim ID
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"

    # 2. Triage Agent (ReAct Loop)
    triage_assessment, agent_trace = run_triage_react_loop(
        claim_id=claim_id,
        images=loaded_images,
        description=description,
        pdf_text=pdf_text,
        policy_type=policy_type or "standard_homeowner"
    )

    # 3. Output Safety Checker (sanitize or regenerate per requirement 1.3)
    _, safety_checks, sanitized_assessment = evaluate_and_sanitize_safety(triage_assessment)

    response_payload = {
        "claim_id": claim_id,
        "intake_validation": intake_val,
        "triage_assessment": sanitized_assessment,
        "safety_checks": safety_checks
    }

    # Store in memory for retrieval
    claims_db[claim_id] = response_payload
    traces_db[claim_id] = agent_trace

    return response_payload


@app.get("/api/v1/claims/{claim_id}")
def get_claim(claim_id: str):
    if claim_id not in claims_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return claims_db[claim_id]


@app.get("/api/v1/agent/trace/{claim_id}")
def get_agent_trace(claim_id: str):
    if claim_id not in traces_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return traces_db[claim_id]
