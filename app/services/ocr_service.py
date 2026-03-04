import httpx
import base64
import json
from app.core.config import settings, logger

async def solve_captcha_mistral(client: httpx.AsyncClient, image_bytes: bytes) -> str:
    """
    Convierte la imagen en Base64 y solicita la resolución a Mistral OCR.
    """
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    payload = {
        "model": "mistral-ocr-latest",
        "document": {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_b64}"},
        "document_annotation_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "captcha_text_only",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"raw_text": {"type": "string"}},
                    "required": ["raw_text"],
                    "additionalProperties": False
                }
            }
        }
    }

    try:
        resp = await client.post(
            "https://api.mistral.ai/v1/ocr",
            headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"},
            json=payload,
            timeout=45
        )
        resp.raise_for_status()
        data = resp.json()
        
        annotation_str = data.get("document_annotation", "{}")
        annotation = json.loads(annotation_str)
        
        return annotation.get("raw_text", "").strip().replace(" ", "")
    
    except Exception as e:
        logger.error(f"❌ Error en Mistral OCR: {str(e)}")
        raise e