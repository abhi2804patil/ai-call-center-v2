import asyncio
import json
import logging
import time

import google.generativeai as genai

from app.config import get_settings

logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    pass


class GeminiTimeoutError(GeminiAPIError):
    pass


class GeminiIntentClassifier:
    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=256,
                response_mime_type="application/json",
            ),
        )
        self.summary_model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=500,
            ),
        )

    async def classify_intent(
        self,
        customer_text: str,
        possible_intents: dict[str, list[str]],
        language_hint: str = "auto",
    ) -> dict:
        start_time = time.time()

        intent_lines = ""
        for intent, keywords in possible_intents.items():
            intent_lines += f'- "{intent}": similar to [{", ".join(keywords)}]\n'

        prompt = f"""You are an intent classifier for an Indian language phone call. The customer said: "{customer_text}"
The customer is likely speaking in {language_hint}.

Classify this into ONE of these intents based on semantic meaning (not just exact keyword match):
{intent_lines}- "fallback": ONLY if the text is truly unintelligible or completely unrelated
- "transfer": if customer asks for human agent, manager, or wants to complain

IMPORTANT: Any affirmative response like "haan", "ha", "ji", "yes", "ok", "theek hai", "batao", "jaanna hai" should be classified as "interested" with high confidence. Be generous with matching — this is a phone call with informal speech.

Respond with ONLY a JSON object: {{"intent": "intent_name", "confidence": 0.0-1.0}}"""

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            elapsed = time.time() - start_time

            response_text = response.text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            result = json.loads(response_text)

            if result.get("confidence", 0) < 0.2:
                result["intent"] = "fallback"

            logger.info(
                f"Intent classified: text='{customer_text[:50]}', "
                f"intent={result['intent']}, confidence={result.get('confidence', 0):.2f}, "
                f"latency={elapsed:.2f}s"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Gemini returned non-JSON response: {e}")
            return {"intent": "fallback", "confidence": 0.0}
        except Exception as e:
            logger.error(f"Gemini classify_intent error: {e}")
            raise GeminiAPIError(f"Intent classification failed: {e}")

    async def generate_call_summary(self, transcript: list[dict]) -> dict:
        start_time = time.time()

        transcript_text = ""
        for entry in transcript:
            role = entry.get("role", "unknown")
            text = entry.get("text", "")
            transcript_text += f"{role}: {text}\n"

        prompt = f"""Analyze this phone call transcript and provide a summary.

Transcript:
{transcript_text}

Respond with ONLY a JSON object:
{{
  "summary": "Brief 2-3 sentence summary of the call",
  "sentiment": <float from -1.0 (very negative) to 1.0 (very positive)>,
  "outcome_tags": ["list", "of", "relevant", "tags"],
  "action_items": ["list", "of", "follow-up", "actions"]
}}
No other text."""

        try:
            response = await asyncio.to_thread(self.summary_model.generate_content, prompt)
            elapsed = time.time() - start_time

            response_text = response.text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            result = json.loads(response_text)
            logger.info(f"Call summary generated in {elapsed:.2f}s")
            return result

        except json.JSONDecodeError:
            logger.error("Gemini returned non-JSON summary response")
            return {
                "summary": "Call summary unavailable",
                "sentiment": 0.0,
                "outcome_tags": [],
                "action_items": [],
            }
        except Exception as e:
            logger.error(f"Gemini generate_call_summary error: {e}")
            raise GeminiAPIError(f"Summary generation failed: {e}")

    async def detect_language_intent(self, text: str) -> str:
        prompt = f"""What language is this text in? "{text}"
Respond with ONLY the ISO language code (hi, en, ta, te, bn, gu, kn, ml, mr, od, pa).
No other text."""

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            lang_code = response.text.strip().lower()[:2]
            valid_codes = {"hi", "en", "ta", "te", "bn", "gu", "kn", "ml", "mr", "od", "pa"}
            if lang_code in valid_codes:
                return lang_code
            return "hi"
        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return "hi"
