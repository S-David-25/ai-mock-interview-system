import json
import logging
import re
from typing import Optional, Dict, Any, Type
import httpx
from pydantic import BaseModel
from app.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("gemini_service")

# Attempt SDK import if available in runtime environment
_genai_client = None
try:
    from google import genai
    if GEMINI_API_KEY:
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Google GenAI SDK client initialized.")
except Exception as e:
    logger.debug(f"Google GenAI SDK not initialized directly: {e}")

class GeminiService:
    """
    Centralized service for invoking Google Gemini API with structured JSON validation,
    strict error handling, timeout recovery, and deterministic offline resilience.
    """

    @staticmethod
    def is_configured() -> bool:
        return bool(GEMINI_API_KEY and len(GEMINI_API_KEY.strip()) > 5)

    @staticmethod
    async def generate_structured_json(
        prompt: str,
        system_instruction: Optional[str] = None,
        response_model: Optional[Type[BaseModel]] = None,
        temperature: float = 0.2,
        timeout_seconds: float = 25.0
    ) -> Dict[str, Any]:
        """
        Sends structured query to Gemini and parses the resulting JSON payload.
        Ensures output matches expected Pydantic schema or schema structure.
        """
        if not GeminiService.is_configured():
            logger.warning("Gemini API key is not configured. Falling back to local NLP heuristics.")
            raise ValueError("GEMINI_API_KEY is not configured in backend environment.")

        # 1. Try Google GenAI SDK
        if _genai_client is not None:
            try:
                config_params = {
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                }
                if system_instruction:
                    config_params["system_instruction"] = system_instruction

                response = _genai_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=config_params
                )

                raw_text = response.text if hasattr(response, "text") else str(response)
                parsed = GeminiService._clean_and_parse_json(raw_text)
                if response_model:
                    validated = response_model.parse_obj(parsed)
                    return validated.dict()
                return parsed
            except Exception as e:
                logger.error(f"GenAI SDK call failed: {str(e)}")

        # 2. Try REST API via httpx
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "responseMimeType": "application/json"
                }
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 400:
                    raise ValueError("Invalid Gemini API request or key.")
                elif res.status_code == 429:
                    raise ValueError("Gemini API rate limit exceeded. Please retry in a few moments.")
                elif res.status_code != 200:
                    raise ValueError(f"Gemini API returned status {res.status_code}: {res.text}")

                data = res.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise ValueError("Gemini returned an empty candidates response.")

                raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                parsed = GeminiService._clean_and_parse_json(raw_text)
                if response_model:
                    validated = response_model.parse_obj(parsed)
                    return validated.dict()
                return parsed
        except Exception as e:
            logger.error(f"Gemini REST call failed: {str(e)}")
            raise e

    @staticmethod
    def _clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
        """Strips markdown code blocks, cleans whitespace, and parses JSON."""
        if not raw_text or not raw_text.strip():
            raise ValueError("Empty response received from Gemini.")

        cleaned = raw_text.strip()
        # Remove ```json ... ``` wrappers
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Attempt to extract first JSON object via regex
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            raise ValueError(f"Malformed JSON returned by Gemini: {str(e)}")
