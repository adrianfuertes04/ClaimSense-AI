import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from config import QDRANT_URL, QDRANT_COLLECTION, KNOWLEDGE_BASE_DIR, EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)

# Global instances
_qdrant_client: Optional[QdrantClient] = None
_embedding_model: Any = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from fastembed import TextEmbedding
            logger.info("Using FastEmbed (BAAI/bge-small-en-v1.5)")
            _embedding_model = ("fastembed", TextEmbedding(model_name="BAAI/bge-small-en-v1.5"))
        except Exception:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer: {EMBEDDING_MODEL_NAME}")
            _embedding_model = ("sentence_transformers", SentenceTransformer(EMBEDDING_MODEL_NAME))
    return _embedding_model


def embed_text(text: str) -> List[float]:
    model_type, model_instance = get_embedding_model()
    if model_type == "fastembed":
        embeddings = list(model_instance.embed([text]))
        return embeddings[0].tolist()
    else:
        return model_instance.encode(text).tolist()




def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        logger.info(f"Connecting to Qdrant at {QDRANT_URL}")
        _qdrant_client = QdrantClient(url=QDRANT_URL, timeout=10.0)
    return _qdrant_client


def is_qdrant_connected() -> bool:
    try:
        client = get_qdrant_client()
        client.get_collections()
        return True
    except Exception as exc:
        logger.warning(f"Qdrant connection check failed: {exc}")
        return False


def init_knowledge_base():
    """
    Initializes Qdrant collection and indexes historical claims if not already done.
    """
    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections
        exists = any(c.name == QDRANT_COLLECTION for c in collections)
        
        vector_size = 384  # all-MiniLM-L6-v2 dimension
        
        if not exists:
            logger.info(f"Creating collection {QDRANT_COLLECTION}")
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=qmodels.VectorParams(
                    size=vector_size,
                    distance=qmodels.Distance.COSINE
                )
            )
            
        info = client.get_collection(collection_name=QDRANT_COLLECTION)
        points_count = info.points_count or 0
        
        # Load claims from files
        claim_files = sorted(KNOWLEDGE_BASE_DIR.glob("*.json"))
        if not claim_files:
            logger.warning(f"No knowledge base files found in {KNOWLEDGE_BASE_DIR}")
            return
            
        if points_count < len(claim_files) * 0.8:
            logger.info(f"Ingesting {len(claim_files)} historical claims into Qdrant...")
            
            points = []

            for idx, file_path in enumerate(claim_files):
                try:
                    data = json.loads(file_path.read_text(encoding="utf-8-sig"))
                    claim_id = data.get("claim_id", file_path.stem)
                    
                    # Construct representative text
                    text_parts = [
                        f"Claim ID: {claim_id}",
                        f"Damage Type: {data.get('damage_type', '')}",
                        f"Severity: {data.get('severity', '')}",
                        f"Description: {data.get('description', '')}",
                        f"Affected Areas: {', '.join(data.get('affected_areas', []))}",
                        f"Adjuster Notes: {data.get('adjuster_notes', '')}"
                    ]
                    full_text = " | ".join(text_parts)
                    embedding = embed_text(full_text)
                    
                    # Deterministic UUID for Qdrant point
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, claim_id))
                    
                    points.append(
                        qmodels.PointStruct(
                            id=point_id,
                            vector=embedding,
                            payload={
                                **data,
                                "claim_id": claim_id,
                                "search_text": full_text
                            }
                        )
                    )
                except Exception as e:
                    logger.error(f"Error parsing claim {file_path}: {e}")
                    
            if points:
                client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=points
                )
                logger.info(f"Successfully indexed {len(points)} claims into {QDRANT_COLLECTION}")
        else:
            logger.info(f"Collection {QDRANT_COLLECTION} already has {points_count} points.")
    except Exception as exc:
        logger.error(f"Failed to initialize knowledge base in Qdrant: {exc}")


def search_similar_claims(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Searches Qdrant vector store for similar claims.
    Returns list of matching claims with normalized similarity_score.
    """
    try:
        client = get_qdrant_client()
        query_vector = embed_text(query)
        
        result = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=query_vector,
            limit=limit
        )
        search_results = result.points
        
        results = []
        for hit in search_results:
            payload = hit.payload or {}
            claim_id = payload.get("claim_id")
            if not claim_id:
                continue
                
            # Cosine similarity in Qdrant is [-1, 1], map to [0, 1]
            raw_score = float(hit.score)
            normalized_score = round(max(0.0, min(1.0, (raw_score + 1.0) / 2.0 if raw_score < 0 else raw_score)), 4)
            
            res_summary = payload.get("resolution", "")
            notes = payload.get("adjuster_notes", "")
            summary = f"{res_summary.replace('_', ' ').capitalize()}: {notes[:140]}..." if notes else res_summary
            
            results.append({
                "claim_id": claim_id,
                "similarity_score": normalized_score,
                "resolution_summary": summary,
                "damage_type": payload.get("damage_type"),
                "severity": payload.get("severity"),
                "repair_cost_actual": payload.get("repair_cost_actual"),
                "affected_areas": payload.get("affected_areas", [])
            })
            
        return results
    except Exception as exc:
        logger.error(f"Error searching similar claims: {exc}")
        return []
