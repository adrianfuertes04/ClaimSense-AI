import json
import logging
import base64
from typing import List, Dict, Any, Optional
from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

_openai_client: Optional[OpenAI] = None


def get_llm_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        headers = {}
        if "portkey" in LLM_BASE_URL.lower():
            headers["x-portkey-api-key"] = LLM_API_KEY

        _openai_client = OpenAI(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            default_headers=headers if headers else None
        )
    return _openai_client


def is_llm_configured() -> bool:
    return bool(LLM_API_KEY and LLM_BASE_URL and LLM_MODEL)


def encode_image_base64(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def chat_completion(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.1,
    response_format: Optional[Dict[str, str]] = None,
    max_tokens: int = 1500
) -> str:
    """
    Executes a chat completion request to the configured LLM endpoint.
    """
    client = get_llm_client()
    use_model = model or LLM_MODEL
    
    # Reasoning models (gpt-5, o1, o3, o4) require max_completion_tokens
    is_reasoning = any(m in use_model.lower() for m in ["gpt-5", "o1", "o3", "o4"])
    
    kwargs = {
        "model": use_model,
        "messages": messages,
    }
    
    if response_format:
        kwargs["response_format"] = response_format
        
    if is_reasoning:
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature
        
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""
