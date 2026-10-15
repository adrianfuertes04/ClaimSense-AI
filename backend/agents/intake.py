import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from llm_client import chat_completion, encode_image_base64

logger = logging.getLogger(__name__)


def validate_intake(
    images: List[Tuple[bytes, str]],
    description: Optional[str] = None
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Validates intake data.
    Returns: (is_valid: bool, intake_validation_dict: dict, error_message: str)
    """
    has_images = bool(images)
    has_description = bool(description and description.strip())
    
    if not has_images and not has_description:
        return False, {
            "is_property_damage": False,
            "is_valid_image": None,
            "no_pii_detected": True,
            "no_offensive_content": True
        }, "At least one image or a non-empty description is required."

    # Text-only submission
    if not has_images:
        prompt = f"""
You are an insurance intake validation agent. Evaluate this text-only damage claim description:
"{description}"

Determine:
1. is_property_damage (boolean): Does the text describe physical property or structural damage to a building/home?
2. no_pii_detected (boolean): Is there any personal identity or payment info mentioned? (Usually true unless credit card numbers or SSNs are present).
3. no_offensive_content (boolean): Is the text respectful and free of offensive/harmful content?

Respond ONLY with valid JSON in this format:
{{
  "is_property_damage": true,
  "no_pii_detected": true,
  "no_offensive_content": true,
  "reason": ""
}}
"""
        try:
            raw_response = chat_completion([{"role": "user", "content": prompt}])
            cleaned = raw_response.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)
            val = {
                "is_property_damage": bool(data.get("is_property_damage", True)),
                "is_valid_image": None,
                "no_pii_detected": bool(data.get("no_pii_detected", True)),
                "no_offensive_content": bool(data.get("no_offensive_content", True))
            }
            is_ok = val["is_property_damage"] and val["no_pii_detected"] and val["no_offensive_content"]
            reason = data.get("reason", "Text did not describe property damage.") if not is_ok else ""
            return is_ok, val, reason
        except Exception as e:
            logger.error(f"Error in text intake validation: {e}")
            val = {
                "is_property_damage": True,
                "is_valid_image": None,
                "no_pii_detected": True,
                "no_offensive_content": True
            }
            return True, val, ""

    # Multi-modal / Image submission
    user_content: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": f"""You are an insurance claim intake validator. Inspect the attached image(s) and description ("{description or ''}").
Evaluate strictly against these criteria:
1. is_property_damage: true if the photo shows real physical/structural damage to residential property (e.g. water leaks, broken drywall, fire, storm damage, vandalism, burglary damage). FALSE if the photo shows pets, animals, regular furniture without damage, nature, cars, credit cards, or non-damaged scenes.
2. is_valid_image: true if the photo is clear enough to inspect damage. FALSE if it is excessively blurry, motion-blurred, completely dark, indiscernible, or an irrelevant screenshot.
3. no_pii_detected: FALSE if a credit card, debit card, bank card, driver's license, passport, or visible SSN is shown in the image. TRUE if no payment card or sensitive PII is visible.
4. no_offensive_content: true if acceptable; false if offensive/hateful/inappropriate.

CRITICAL INSTRUCTIONS:
- If a credit card or payment card is visible (even a test/fictional card), no_pii_detected MUST be false.
- If the image is heavily motion-blurred or unreadable, is_valid_image MUST be false.
- If the photo shows a pet, animal, or undamaged scene, is_property_damage MUST be false.

Respond ONLY with valid JSON in this exact structure:
{{
  "is_property_damage": true,
  "is_valid_image": true,
  "no_pii_detected": true,
  "no_offensive_content": true,
  "reason": "Clear explanation if any check is false"
}}
"""
        }
    ]

    # Add images
    for img_bytes, mime in images[:3]:  # inspect up to first 3 views
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": encode_image_base64(img_bytes, mime)
            }
        })

    try:
        raw_response = chat_completion([{"role": "user", "content": user_content}])
        cleaned = raw_response.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        
        val = {
            "is_property_damage": bool(data.get("is_property_damage", False)),
            "is_valid_image": bool(data.get("is_valid_image", True)),
            "no_pii_detected": bool(data.get("no_pii_detected", True)),
            "no_offensive_content": bool(data.get("no_offensive_content", True))
        }
        
        is_ok = (
            val["is_property_damage"] is True and
            val["is_valid_image"] is True and
            val["no_pii_detected"] is True and
            val["no_offensive_content"] is True
        )
        
        reason = data.get("reason", "Intake validation failed.") if not is_ok else ""
        return is_ok, val, reason
    except Exception as e:
        logger.error(f"Error during multimodal intake validation: {e}")
        # Default fallback
        val = {
            "is_property_damage": True,
            "is_valid_image": True,
            "no_pii_detected": True,
            "no_offensive_content": True
        }
        return True, val, ""
