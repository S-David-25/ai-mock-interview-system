import asyncio
import json
import logging
import re
import time
from typing import Optional, Dict, Any, Type
import httpx
from pydantic import BaseModel
from app.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("gemini_service")

class GeminiService:
    """
    Centralized service for invoking Google Gemini API with structured JSON validation,
    fast primary-model execution via direct async REST, at most ONE fallback attempt,
    duration logging, and strict error reporting without hardcoded templates.
    """

    # Dynamic active model cache (defaults to configured model)
    _active_model: Optional[str] = None

    # Fallback candidates ordered by speed & availability
    FALLBACK_CANDIDATES = [
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ]

    @staticmethod
    def is_configured() -> bool:
        return bool(GEMINI_API_KEY and len(GEMINI_API_KEY.strip()) > 5)

    @classmethod
    def get_active_model(cls) -> str:
        if cls._active_model:
            return cls._active_model
        return GEMINI_MODEL or "gemini-3.5-flash-lite"

    @classmethod
    def set_active_model(cls, model_name: str) -> None:
        cls._active_model = model_name

    @staticmethod
    async def generate_structured_json(
        prompt: str,
        system_instruction: Optional[str] = None,
        response_model: Optional[Type[BaseModel]] = None,
        temperature: float = 0.4,
        timeout_seconds: float = 15.0,
        purpose: str = "General Generation"
    ) -> Dict[str, Any]:
        """
        Sends structured query to Gemini REST API and parses the resulting JSON payload.
        Uses primary model directly. If it fails (429/404/503), tries at most ONE fallback model.
        Logs precise request start, model, duration, and completion.
        """
        if not GeminiService.is_configured():
            logger.error("Gemini API key is not configured in environment (GEMINI_API_KEY is empty).")
            raise ValueError("GEMINI_API_KEY is not configured in backend environment.")

        # Determine primary model and at most ONE fallback model
        primary_model = GeminiService.get_active_model()
        
        # Pick the best fallback candidate that is different from primary
        fallback_model = None
        for cand in GeminiService.FALLBACK_CANDIDATES:
            if cand != primary_model:
                fallback_model = cand
                break

        models_to_try = [primary_model]
        if fallback_model:
            models_to_try.append(fallback_model)

        last_error = None

        for attempt_idx, model_name in enumerate(models_to_try):
            is_fallback_attempt = (attempt_idx > 0)
            t_start = time.time()

            logger.info(f"[Gemini] request started: purpose={purpose}")
            logger.info(f"[Gemini] model={model_name}")

            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
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
                    t_elapsed = time.time() - t_start

                    if res.status_code != 200:
                        logger.warning(f"[Gemini] request failed: status={res.status_code}")
                        last_error = ValueError(f"Gemini API returned HTTP {res.status_code} for {model_name}: {res.text[:120]}")
                        # If primary model failed and fallback exists, try fallback
                        if not is_fallback_attempt and fallback_model:
                            if res.status_code == 429:
                                await asyncio.sleep(0.8)
                            logger.info(f"[Gemini] Primary model {model_name} failed with status {res.status_code}. Trying single fallback: {fallback_model}...")
                            continue
                        break

                    data = res.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        logger.warning(f"[Gemini] request failed: status=empty_candidates")
                        last_error = ValueError(f"Gemini model {model_name} returned empty candidates.")
                        if not is_fallback_attempt and fallback_model:
                            continue
                        break

                    raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    parsed = GeminiService._clean_and_parse_json(raw_text)
                    logger.info(f"[Gemini] request completed: purpose={purpose} duration={t_elapsed:.2f}s")

                    # If fallback succeeded, remember it as active model for future requests
                    if is_fallback_attempt:
                        GeminiService.set_active_model(model_name)

                    if response_model:
                        validated = response_model.parse_obj(parsed)
                        return validated.dict()
                    return parsed
            except Exception as e:
                t_elapsed = time.time() - t_start
                logger.warning(f"[Gemini] request failed: error={e} duration={t_elapsed:.2f}s")
                last_error = e
                if not is_fallback_attempt and fallback_model:
                    logger.info(f"[Gemini] Primary model {model_name} error ({e}). Trying single fallback: {fallback_model}...")
                    continue
                break

        logger.error(f"[Gemini] Generation failed. Last error: {last_error}")
        raise ValueError(f"Gemini API call failed: {str(last_error)}")

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
