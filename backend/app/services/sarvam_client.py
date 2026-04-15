import asyncio
import base64
import io
import logging
import struct
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class SarvamAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class SarvamTimeoutError(SarvamAPIError):
    pass


class SarvamRateLimitError(SarvamAPIError):
    pass


SARVAM_LANGUAGES = {
    "hi": "Hindi",
    "bn": "Bengali",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "od": "Odia",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
    "en": "English",
}

# Sarvam API requires full locale codes (e.g. "hi-IN" not "hi")
_LANG_TO_LOCALE = {
    "hi": "hi-IN", "bn": "bn-IN", "gu": "gu-IN", "kn": "kn-IN",
    "ml": "ml-IN", "mr": "mr-IN", "od": "od-IN", "pa": "pa-IN",
    "ta": "ta-IN", "te": "te-IN", "en": "en-IN",
}


def _normalize_lang(code: str) -> str:
    """Convert short language codes to full Sarvam locale codes."""
    if "-" in code:
        return code  # Already a locale like "hi-IN"
    return _LANG_TO_LOCALE.get(code, f"{code}-IN")


class SarvamClient:
    BASE_URL = "https://api.sarvam.ai"

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.SARVAM_API_KEY
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "api-subscription-key": self.api_key,
            },
        )

    async def text_to_speech(
        self,
        text: str,
        language_code: str,
        voice: str = "priya",
        model: str = "bulbul:v3-beta",
        sample_rate: int = 8000,
    ) -> tuple[bytes, int]:
        start_time = time.time()
        language_code = _normalize_lang(language_code)
        url = f"{self.BASE_URL}/text-to-speech"
        payload = {
            "inputs": [text],
            "target_language_code": language_code,
            "speaker": voice,
            "model": model,
            "speech_sample_rate": sample_rate,
            "enable_preprocessing": False,
        }

        response = await self._request_with_retry("POST", url, json=payload)
        elapsed = time.time() - start_time

        data = response.json()
        audio_base64 = data["audios"][0]
        audio_bytes = base64.b64decode(audio_base64)
        duration_ms = self._calculate_wav_duration(audio_bytes, sample_rate)

        logger.info(
            f"TTS completed: lang={language_code}, voice={voice}, "
            f"text_len={len(text)}, duration={duration_ms}ms, latency={elapsed:.2f}s"
        )
        return audio_bytes, duration_ms

    async def speech_to_text(
        self,
        audio_data: bytes,
        language_code: str = "auto",
    ) -> dict:
        start_time = time.time()
        if language_code != "auto":
            language_code = _normalize_lang(language_code)
        url = f"{self.BASE_URL}/speech-to-text"

        files = {"file": ("audio.wav", io.BytesIO(audio_data), "audio/wav")}
        data = {
            "language_code": language_code,
            "model": "saarika:v2.5",
        }

        response = await self._request_with_retry("POST", url, data=data, files=files)
        elapsed = time.time() - start_time

        result = response.json()
        logger.info(
            f"STT completed: lang={language_code}, "
            f"text_len={len(result.get('transcript', ''))}, latency={elapsed:.2f}s"
        )
        return {
            "text": result.get("transcript", ""),
            "language_code": result.get("language_code", language_code),
        }

    async def speech_to_text_translate(
        self,
        audio_data: bytes,
        language_code: str = "auto",
    ) -> dict:
        start_time = time.time()
        url = f"{self.BASE_URL}/speech-to-text-translate"

        files = {"file": ("audio.wav", io.BytesIO(audio_data), "audio/wav")}
        data = {
            "language_code": language_code,
            "model": "saarika:v2.5",
        }

        response = await self._request_with_retry("POST", url, data=data, files=files)
        elapsed = time.time() - start_time

        result = response.json()
        logger.info(
            f"STT+Translate completed: lang={language_code}, latency={elapsed:.2f}s"
        )
        return {
            "transcript": result.get("transcript", ""),
            "translated_text": result.get("translated_text", ""),
            "language_code": result.get("language_code", language_code),
        }

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs,
    ) -> httpx.Response:
        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self.client.request(method, url, **kwargs)

                if response.status_code == 200:
                    return response

                if response.status_code == 429:
                    wait_time = (2**attempt) * 1.0
                    logger.warning(f"Sarvam rate limited, retrying in {wait_time}s (attempt {attempt + 1})")
                    await asyncio.sleep(wait_time)
                    last_error = SarvamRateLimitError(
                        f"Rate limited: {response.text}", response.status_code
                    )
                    continue

                if response.status_code >= 500 and attempt < 1:
                    logger.warning(f"Sarvam server error {response.status_code}, retrying once")
                    await asyncio.sleep(1.0)
                    last_error = SarvamAPIError(
                        f"Server error: {response.text}", response.status_code
                    )
                    continue

                raise SarvamAPIError(
                    f"Sarvam API error {response.status_code}: {response.text}",
                    response.status_code,
                )

            except httpx.TimeoutException:
                last_error = SarvamTimeoutError("Sarvam API request timed out")
                if attempt < max_retries - 1:
                    logger.warning(f"Sarvam timeout, retrying (attempt {attempt + 1})")
                    await asyncio.sleep(1.0)
                    continue
                raise last_error

            except httpx.RequestError as e:
                last_error = SarvamAPIError(f"Request error: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0)
                    continue
                raise last_error

        raise last_error or SarvamAPIError("Max retries exceeded")

    @staticmethod
    def _calculate_wav_duration(audio_bytes: bytes, sample_rate: int = 8000) -> int:
        try:
            if len(audio_bytes) > 44 and audio_bytes[:4] == b"RIFF":
                channels = struct.unpack_from("<H", audio_bytes, 22)[0]
                bits_per_sample = struct.unpack_from("<H", audio_bytes, 34)[0]
                data_size = len(audio_bytes) - 44
                bytes_per_sample = bits_per_sample // 8
                num_samples = data_size // (channels * bytes_per_sample)
                duration_ms = int((num_samples / sample_rate) * 1000)
                return duration_ms
            else:
                bytes_per_sample = 2
                num_samples = len(audio_bytes) // bytes_per_sample
                return int((num_samples / sample_rate) * 1000)
        except Exception:
            return 0

    async def close(self):
        await self.client.aclose()
